#!/usr/bin/env python3
"""Fetch and organize Texas Instruments CMSIS SVD files.

Sources:
  1. TI CMSIS packs listed in the Keil pack index (vendor TexasInstruments)
  2. Keil TM4C_DFP pack (Tiva-C)
  3. github.com/TexasInstruments/ti-simplelink-pacs (official)
  4. github.com/seanmlyons22/ti-lprf-pacs (community)

Incremental: every run starts with a cheap metadata check against
manifest.json (pack versions from index.pidx, repo HEAD SHAs from
git ls-remote). If nothing changed the script prints "up to date" and
exits without downloading any artifact or touching any file. Otherwise
only the changed sources are downloaded and re-extracted, only their
<Family> files are replaced, and manifest.json is updated.

Deleting manifest.json forces a full rebuild.

Stdlib only. Re-runnable: downloads and clones are cached in .work/.

Usage: python fetch.py [--keep-work]
"""

import argparse
import datetime
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORK = ROOT / ".work"
SVD_BASE = ROOT  # family folders live directly at the repo root
LICENSES = ROOT / "LICENSES"
MANIFEST = ROOT / "manifest.json"

# Names at the repo root that are NOT device family folders and must never
# be deleted by the full-rebuild cleanup.
PROTECTED = {
    ".git",
    ".github",
    ".gitignore",
    ".work",
    "LICENSES",
    "README.md",
    "manifest.json",
    "fetch.py",
}

PIDX_URL = "https://www.keil.com/pack/index.pidx"
UA = {"User-Agent": "Mozilla/5.0"}

REPOS = [
    {
        "name": "ti-simplelink-pacs",
        "url": "https://github.com/TexasInstruments/ti-simplelink-pacs",
        "family": None,  # per file, via cc_family()
        "provenance": "pristine",
    },
    {
        "name": "ti-lprf-pacs",
        "url": "https://github.com/seanmlyons22/ti-lprf-pacs",
        "family": None,  # per file, via cc_family()
        "provenance": "community",
    },
]

# Single files fetched raw, without cloning their (large) host repo.
# Version = last commit sha touching the file, via the GitHub commits API.
RAW_SOURCES = [
    {
        "name": "cmsis-svd-data-cc26x0",
        "url": "https://github.com/cmsis-svd/cmsis-svd-data",
        "commits_api": "https://api.github.com/repos/cmsis-svd/cmsis-svd-data/"
                       "commits?path=data/TexasInstruments/CC26x0.svd&per_page=1",
        "raw_url": "https://raw.githubusercontent.com/cmsis-svd/cmsis-svd-data/"
                   "main/data/TexasInstruments/CC26x0.svd",
        "filename": "CC26x0.svd",
        "family": "CC26x0",
        "provenance": "community",
        "license": "no explicit license on the TI files in cmsis-svd-data",
    },
]

issues = []


def log(msg):
    print(msg, flush=True)


def _force_rw(func, path, _exc):
    """rmtree helper: clear the read-only bit git sets on object files
    (needed on Windows), then retry."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def rmtree_robust(path):
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_force_rw)
    else:
        shutil.rmtree(path, onerror=_force_rw)


def clean_family_dirs():
    """Full-rebuild cleanup. The SVD base is now the repo root, so we must
    delete only device family folders and never the repo itself or any
    protected top-level entry (.git, LICENSES, fetch.py, ...)."""
    for child in ROOT.iterdir():
        if child.is_dir() and child.name not in PROTECTED:
            rmtree_robust(child)


def http_get_bytes(url, retries=3):
    """Fetch url into memory. Used for metadata (index.pidx) only."""
    last = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            log(f"  attempt {attempt}/{retries} failed for {url}: {e}")
    raise RuntimeError(f"metadata fetch failed: {url}: {last}")


def http_get(url, dest, retries=3):
    """Download url to dest (Path). Skips if dest already exists and is non-empty."""
    if dest.exists() and dest.stat().st_size > 0:
        log(f"  cached: {dest.name}")
        return
    tmp = dest.with_suffix(dest.suffix + ".part")
    last = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
                shutil.copyfileobj(r, f, 1 << 20)
            tmp.replace(dest)
            log(f"  artifact download: {dest.name} ({dest.stat().st_size // 1024} KiB)")
            return
        except Exception as e:  # noqa: BLE001
            last = e
            log(f"  attempt {attempt}/{retries} failed for {url}: {e}")
    raise RuntimeError(f"download failed: {url}: {last}")


def family_for_pack(name):
    for prefix, fam in (
        ("MSPM0", "MSPM0"),
        ("MSPM33", "MSPM33"),
        ("MSPS003", "MSPS003"),
        ("MSP432E", "MSP432E4"),
        ("MSP432P", "MSP432P4"),
        ("TM4C", "TM4C"),
    ):
        if name.upper().startswith(prefix):
            return fam
    return name  # unexpected pack name, keep it visible


def cc_family(fname):
    """TI SimpleLink family from the SVD filename. Layout is always by
    device family; provenance (official vs community) lives in the
    manifest, not in the folder structure."""
    stem = fname.lower()
    if stem.endswith(".svd"):
        stem = stem[:-4]
    for prefix, fam in (
        ("cc13x0", "CC13x0"),
        ("cc26x0", "CC26x0"),
        ("cc2640r2", "CC26x0R2"),
        ("cc13x1_cc26x1", "CC13x1_CC26x1"),
        ("cc13x2x7_cc26x2x7", "CC13x2x7_CC26x2x7"),
        ("cc13x2", "CC13x2_CC26x2"),
        ("cc13x4_cc26x4", "CC13x4_CC26x4"),
        ("cc23", "CC23x0"),
        ("cc27", "CC27xx"),
    ):
        if stem.startswith(prefix):
            return fam
    return "SimpleLink"  # unexpected name, keep it visible

def license_label(text):
    t = text.lower()
    if "bsd-3-clause" in t or (
        "redistribution and use in source and binary forms" in t
        and "neither the name" in t
    ):
        return "BSD-3-Clause"
    if "apache license" in t and "version 2.0" in t:
        return "Apache-2.0"
    if "mit license" in t:
        return "MIT"
    return "unspecified (see LICENSES/)"


def version_key(v):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:4])


def extract_pack(pack_path, source_name, out_dir):
    """Extract all *.svd from a .pack (zip) into out_dir (flat).
    Returns (list of Paths, license text or None)."""
    svds = []
    lic_text = None
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(pack_path) as z:
        names = z.namelist()
        svd_names = [n for n in names if n.lower().endswith(".svd")]
        lic_candidates = sorted(
            (
                n
                for n in names
                if "license" in Path(n).name.lower()
                and Path(n).suffix.lower() in ("", ".txt", ".md")
            ),
            key=len,
        )
        for n in svd_names:
            dest = out_dir / Path(n).name
            data = z.read(n)
            if dest.exists() and dest.read_bytes() != data:
                issues.append(
                    f"{source_name}: two different files named {dest.name} "
                    "inside one pack, kept the first"
                )
                continue
            dest.write_bytes(data)
            svds.append(dest)
        if lic_candidates:
            lic_text = z.read(lic_candidates[0]).decode("utf-8", errors="replace")
            lic_out = LICENSES / f"{source_name}-LICENSE.txt"
            lic_out.write_text(lic_text, encoding="utf-8")
    return svds, lic_text


def clone_repo(url, dest):
    if (dest / ".git").exists():
        log(f"  cached clone: {dest.name}")
    else:
        log(f"  artifact download: git clone {url}")
        subprocess.run(
            ["git", "clone", "--depth", "1", url, str(dest)],
            check=True,
        )
    sha = subprocess.run(
        ["git", "-C", str(dest), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return sha


def ls_remote_head(url):
    """Cheap metadata check: HEAD sha of a remote repo."""
    out = subprocess.run(
        ["git", "ls-remote", url, "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "HEAD":
            return parts[0]
    raise RuntimeError(f"git ls-remote returned no HEAD for {url}")


def validate_svd(path):
    """Return None if OK, else an error string."""
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as e:
        return f"XML parse error: {e}"
    tag = root.tag.split("}")[-1]
    if tag != "device":
        return f"root element is '{tag}', expected 'device'"
    return None


def load_manifest():
    if not MANIFEST.exists():
        return None
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        log("manifest.json unreadable, forcing full rebuild")
        return None


def index_packs(pidx_bytes):
    """Parse index.pidx, return the pack entries this repo tracks."""
    packs = []
    for pdsc in ET.fromstring(pidx_bytes).iter("pdsc"):
        vendor = pdsc.get("vendor", "")
        name = pdsc.get("name", "")
        version = pdsc.get("version", "")
        url = pdsc.get("url", "")
        if vendor == "TexasInstruments":
            packs.append((vendor, name, version, url, "pristine"))
        elif vendor == "Keil" and name == "TM4C_DFP":
            packs.append((vendor, name, version, url, "pristine"))
    return packs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep-work", action="store_true", help="keep .work/ cache")
    args = ap.parse_args()

    old = load_manifest()
    full = old is None or not SVD_BASE.is_dir()
    old_sources = {s["name"]: s for s in old["sources"]} if old else {}
    old_files = old["files"] if old else []

    # a source whose recorded files are missing on disk must be refetched
    broken = set()
    if not full:
        for rec in old_files:
            if not (ROOT / rec["path"]).is_file():
                broken.add(rec["source"])
        for name in sorted(broken):
            log(f"{name}: recorded files missing on disk, will refetch")

    # ---- 1. metadata check (no artifact downloads) ----------------------
    log("metadata: fetching pack index")
    pidx_bytes = http_get_bytes(PIDX_URL)
    log(f"metadata: index.pidx ({len(pidx_bytes) // 1024} KiB)")
    packs = index_packs(pidx_bytes)
    log(f"found {len(packs)} packs in index")

    changed_packs = []
    for vendor, name, version, url, prov in packs:
        source_name = f"{vendor}.{name}"
        rec = old_sources.get(source_name)
        if full or rec is None or rec.get("version") != version \
                or source_name in broken:
            changed_packs.append((vendor, name, version, url, prov))

    index_names = {f"{v}.{n}" for v, n, _, _, _ in packs}
    repo_names = {r["name"] for r in REPOS}
    for sname in old_sources:
        if sname not in index_names and sname not in repo_names:
            log(f"warning: {sname} no longer listed in the pack index, "
                "keeping its existing files")

    changed_repos = []
    for repo in REPOS:
        head = ls_remote_head(repo["url"])
        log(f"metadata: ls-remote {repo['name']} -> {head}")
        rec = old_sources.get(repo["name"])
        if full or rec is None or rec.get("version") != head \
                or repo["name"] in broken:
            changed_repos.append(repo)

    changed_raw = []
    for raw in RAW_SOURCES:
        try:
            data = json.loads(http_get_bytes(raw["commits_api"]))
            head = data[0]["sha"] if data else ""
        except Exception as e:
            issues.append(f"{raw['name']}: commits API failed: {e}")
            head = ""
        log(f"metadata: commits API {raw['name']} -> {head or '?'}")
        rec = old_sources.get(raw["name"])
        if full or rec is None or (head and rec.get("version") != head):
            raw["_head"] = head
            changed_raw.append(raw)

    if not changed_packs and not changed_repos and not changed_raw:
        log("up to date")
        return 0

    log(f"{len(changed_packs)} pack(s), {len(changed_repos)} repo(s) and "
        f"{len(changed_raw)} raw file(s) changed")

    # ---- 2. download + extract only the changed sources ------------------
    for d in (WORK, WORK / "packs", WORK / "repos", LICENSES):
        d.mkdir(parents=True, exist_ok=True)
    if full:
        # SVD base is the repo root: delete only family folders, never the
        # repo itself or any protected entry.
        clean_family_dirs()

    ingested = {}       # source_name -> new manifest sources[] entry
    changed_names = set()  # sources actually re-ingested this run
    # candidates[(family, filename)] = list of dicts, merged newest-wins below
    candidates = {}

    for vendor, name, version, url, prov in changed_packs:
        if not url.endswith("/"):
            url += "/"
        fname = f"{vendor}.{name}.{version}.pack"
        pack_url = url + fname
        pack_path = WORK / "packs" / fname
        source_name = f"{vendor}.{name}"
        family = family_for_pack(name)
        prev = old_sources.get(source_name, {}).get("version", "new")
        log(f"pack {source_name} {prev} -> {version}")
        try:
            http_get(pack_url, pack_path)
        except RuntimeError as e:
            issues.append(f"{source_name}: {e}")
            continue
        try:
            svds, lic_text = extract_pack(
                pack_path, source_name, WORK / "extracted" / source_name
            )
        except zipfile.BadZipFile as e:
            issues.append(f"{source_name}: bad zip: {e}")
            continue
        if not svds:
            issues.append(f"{source_name}: pack contains no SVD files")
        if vendor == "Keil" and name == "TM4C_DFP":
            lic = "unclear (Keil pack, no license element in pdsc)"
            if lic_text:
                lic = license_label(lic_text)
        else:
            lic = license_label(lic_text) if lic_text else "no license file in pack"
        ingested[source_name] = {
            "name": source_name,
            "url": pack_url,
            "version": version,
            "license": lic,
            "files": 0,  # filled in after dedupe
        }
        changed_names.add(source_name)
        for p in svds:
            candidates.setdefault((family, p.name), []).append(
                {
                    "path": p,
                    "source": source_name,
                    "version": version,
                    "provenance": prov,
                    "new": True,
                }
            )

    # ---- 3. git repos (changed only) -------------------------------------
    for repo in changed_repos:
        log(f"repo {repo['name']}")
        dest = WORK / "repos" / repo["name"]
        try:
            sha = clone_repo(repo["url"], dest)
        except subprocess.CalledProcessError as e:
            issues.append(f"{repo['name']}: git clone failed: {e}")
            continue
        svd_src = dest / "svds"
        svd_files = sorted(svd_src.glob("*.svd")) if svd_src.is_dir() else []
        if not svd_files:
            svd_files = sorted(dest.rglob("*.svd"))
            if svd_files:
                issues.append(
                    f"{repo['name']}: no svds/ dir, used recursive search instead"
                )
        lic = "no license file found"
        for cand in ("LICENSE", "LICENSE.txt", "LICENSE.md", "license.txt"):
            lf = dest / cand
            if lf.exists():
                text = lf.read_text(encoding="utf-8", errors="replace")
                (LICENSES / f"{repo['name']}-{cand}").write_text(
                    text, encoding="utf-8"
                )
                lic = license_label(text)
                break
        ingested[repo["name"]] = {
            "name": repo["name"],
            "url": repo["url"],
            "version": sha,
            "license": lic,
            "files": 0,
        }
        changed_names.add(repo["name"])
        for f in svd_files:
            fam = repo["family"] or cc_family(f.name)
            candidates.setdefault((fam, f.name), []).append(
                {
                    "path": f,
                    "source": repo["name"],
                    "version": sha,
                    "provenance": repo["provenance"],
                    "new": True,
                }
            )

    # ---- 3b. raw single files (changed only) -----------------------------
    for raw in changed_raw:
        log(f"raw file {raw['name']}")
        dest = WORK / "raw" / raw["filename"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            http_get(raw["raw_url"], dest)
        except RuntimeError as e:
            issues.append(f"{raw['name']}: {e}")
            continue
        ingested[raw["name"]] = {
            "name": raw["name"],
            "url": raw["url"],
            "version": raw.get("_head", ""),
            "license": raw["license"],
            "files": 0,
        }
        changed_names.add(raw["name"])
        candidates.setdefault((raw["family"], raw["filename"]), []).append(
            {
                "path": dest,
                "source": raw["name"],
                "version": raw.get("_head", ""),
                "provenance": raw["provenance"],
                "new": True,
            }
        )

    # ---- 4. merge: replace only the files owned by re-ingested sources ---
    # Records from unchanged sources are kept as-is; records owned by a
    # changed source are dropped and rebuilt from the new extraction.
    kept_records = []
    for rec in old_files if not full else []:
        if rec["source"] in changed_names:
            p = ROOT / rec["path"]
            if p.exists():
                p.unlink()
        else:
            kept_records.append(rec)

    existing_by_key = {}
    for rec in kept_records:
        parts = rec["path"].split("/")  # <family>/<filename>
        existing_by_key[(parts[0], parts[1])] = rec

    # TI ships some devices in both a legacy pack (MSPM0G_DFP, MSPM0L_DFP)
    # and its renamed successor. Keep the copy from the pack with the
    # highest version, drop the rest, log what was dropped. On incremental
    # runs the surviving on-disk copy of an unchanged source competes with
    # its recorded pack version.
    new_records = []
    for (family, filename), cands in sorted(candidates.items()):
        all_c = list(cands)
        existing = existing_by_key.get((family, filename))
        if existing is not None:
            all_c.append(
                {
                    "path": ROOT / existing["path"],
                    "source": existing["source"],
                    "version": old_sources.get(existing["source"], {}).get(
                        "version", "0"
                    ),
                    "provenance": existing["provenance"],
                    "new": False,
                }
            )
        if len(all_c) == 1:
            winner = all_c[0]
        else:
            data0 = all_c[0]["path"].read_bytes()
            if all(c["path"].read_bytes() == data0 for c in all_c[1:]):
                winner = next((c for c in all_c if not c["new"]), all_c[0])
                issues.append(
                    f"{family}/{filename}: identical copy in "
                    + ", ".join(c["source"] for c in all_c)
                    + f", kept {winner['source']}"
                )
            else:
                all_c.sort(key=lambda c: version_key(c["version"]), reverse=True)
                winner = all_c[0]
                dropped = ", ".join(
                    f"{c['source']} {c['version']}" for c in all_c[1:]
                )
                issues.append(
                    f"{family}/{filename}: kept {winner['source']} "
                    f"{winner['version']}, dropped older {dropped}"
                )
        if not winner["new"]:
            continue  # existing file stays, nothing to copy
        fam_dir = SVD_BASE / family
        fam_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(winner["path"], fam_dir / filename)
        if existing is not None:
            kept_records.remove(existing)
        new_records.append(
            {
                "path": f"{family}/{filename}",
                "device": Path(filename).stem,
                "family": family,
                "source": winner["source"],
                "provenance": winner["provenance"],
            }
        )

    # ---- 5. validate the new files ---------------------------------------
    log(f"validating {len(new_records)} new SVD files")
    valid_records = []
    for rec in new_records:
        p = ROOT / rec["path"]
        err = validate_svd(p)
        if err:
            issues.append(f"removed {rec['path']}: {err}")
            p.unlink()
        else:
            valid_records.append(rec)
    file_records = sorted(kept_records + valid_records, key=lambda r: r["path"])

    # drop empty family dirs (never touch protected top-level entries)
    for d in list(SVD_BASE.iterdir()):
        if d.is_dir() and d.name not in PROTECTED and not any(d.iterdir()):
            d.rmdir()

    # ---- 6. manifest ------------------------------------------------------
    # keep the old sources[] order, replace re-ingested entries in place,
    # append genuinely new sources at the end
    final_sources = []
    seen = set()
    for s in (old["sources"] if old and not full else []):
        final_sources.append(ingested.get(s["name"], s))
        seen.add(s["name"])
    for sname, s in ingested.items():
        if sname not in seen:
            final_sources.append(s)

    counts = {}
    for rec in file_records:
        counts[rec["source"]] = counts.get(rec["source"], 0) + 1
    for s in final_sources:
        s["files"] = counts.get(s["name"], 0)

    # keep old issues that do not involve a re-ingested source; the run
    # regenerates the ones that do
    old_issues = old.get("issues", []) if old and not full else []
    kept_issues = [
        i for i in old_issues if not any(n in i for n in changed_names)
    ]

    total_bytes = sum((ROOT / r["path"]).stat().st_size for r in file_records)
    manifest = {
        "vendor": "Texas Instruments",
        "generated": datetime.date.today().isoformat(),
        "sources": final_sources,
        "files": file_records,
        "stats": {"total_files": len(file_records), "total_bytes": total_bytes},
        "issues": kept_issues + issues,
    }
    MANIFEST.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    log(
        f"done: {len(changed_names)} source(s) updated, "
        f"{len(file_records)} SVD files, "
        f"{total_bytes / (1 << 20):.1f} MiB, {len(issues)} new issues"
    )
    for i in issues:
        log(f"  issue: {i}")

    if not args.keep_work:
        rmtree_robust(WORK)
    return 0


if __name__ == "__main__":
    sys.exit(main())
