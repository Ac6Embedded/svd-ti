# Texas Instruments SVD collection

Local collection of CMSIS SVD files for TI Arm microcontrollers. Built on 2026-07-19 from the official Keil pack index, TI CMSIS device family packs, the Keil TM4C pack, and two GitHub repos. 113 files, about 306 MiB.

## Coverage

The layout is one folder per TI device family. Provenance (official vs community) is per file, recorded in manifest.json and summarized here.

| Family | Files | What it is | Provenance |
|---|---|---|---|
| MSPM0 | 21 | MSPM0 C/G/L/H series (Cortex-M0+) | official (TI packs) |
| MSPM33 | 1 | MSPM33C321A (Cortex-M33) | official (TI pack) |
| MSPS003 | 1 | MSPS003FX | official (TI pack) |
| MSP432P4 | 8 | MSP432P4xx (Cortex-M4F, discontinued) | official (TI pack) |
| MSP432E4 | 2 | MSP432E4 (Cortex-M4F, discontinued) | official (TI pack) |
| TM4C | 71 | Tiva-C TM4C123/TM4C129 (Cortex-M4F) | Keil pack |
| CC23x0 | 1 | CC2340R2/R5/R53 (Cortex-M0+) | official (TI repo) |
| CC27xx | 1 | CC2745 generation | official (TI repo) |
| CC13x0 | 1 | CC1310/CC1350 | community |
| CC26x0 | 1 | CC2650/CC2640/CC2630 | community |
| CC26x0R2 | 1 | CC2640R2F | community |
| CC13x1_CC26x1 | 1 | CC1311/CC2651 | community |
| CC13x2_CC26x2 | 2 | CC1312/CC1352/CC2642/CC2652 (two upstream variants) | community |
| CC13x2x7_CC26x2x7 | 1 | R7/P7 parts | community |
| CC13x4_CC26x4 | 1 | CC1314/CC1354/CC2674 (Cortex-M33) | community |

## Sources

Pack entries come from https://www.keil.com/pack/index.pidx (vendor TexasInstruments, plus the Keil TM4C_DFP entry). Exact pack URLs are in manifest.json. Summary:

| Source | Version | Files kept |
|---|---|---|
| TexasInstruments.MSPM0G1X0X_G3X0X_DFP | 1.3.1 | 4 |
| TexasInstruments.MSPM0L11XX_L13XX_DFP | 1.3.1 | 3 |
| TexasInstruments.MSPM0L122X_L222X_DFP | 1.1.1 | 2 |
| TexasInstruments.MSPM0GX51X_DFP | 1.0.0 | 2 |
| TexasInstruments.MSPM0GX218_GX207_DFP | 1.0.0 | 4 |
| TexasInstruments.MSPM0G511X_G518X_DFP | 1.0.0 | 2 |
| TexasInstruments.MSPM0L111X_DFP | 1.0.0 | 1 |
| TexasInstruments.MSPM0H321X_DFP | 1.0.0 | 1 |
| TexasInstruments.MSPM0C110X_DFP | 1.2.0 | 2 |
| TexasInstruments.MSPM0G_DFP (legacy) | 1.2.1 | 0, superseded |
| TexasInstruments.MSPM0L_DFP (legacy) | 1.2.1 | 0, superseded |
| TexasInstruments.MSPS003FX_DFP | 1.1.1 | 1 |
| TexasInstruments.MSPM33C321A_DFP | 1.0.0 | 1 |
| TexasInstruments.MSP432P4xx_DFP | 3.2.6 | 8 |
| TexasInstruments.MSP432E4_DFP | 3.2.6 | 2 |
| Keil.TM4C_DFP | 1.1.0 | 71 |
| github.com/TexasInstruments/ti-simplelink-pacs | commit 6e4d2b84a999cf0773d39bc50b28a8be1a500fd9 (2026-04-23) | 2 |
| github.com/seanmlyons22/ti-lprf-pacs | commit 4220b29917f59c053a66f09bfb9dcac0d6dce0a2 (2024-12-09) | 7 |
| github.com/cmsis-svd/cmsis-svd-data (CC26x0.svd only) | commit 22f50f4b4d5e7268eb6ba49e2fdb4735cf14be4d | 1 |

## Dedupe

TI publishes the same MSPM0 devices in a legacy pack and in its renamed successor. Both are still in the index. fetch.py keeps the copy from the pack with the higher version and drops the older one:

- MSPM0G110X, MSPM0G150X, MSPM0G310X, MSPM0G350X: kept from MSPM0G1X0X_G3X0X_DFP 1.3.1, dropped MSPM0G_DFP 1.2.1
- MSPM0L110X, MSPM0L130X, MSPM0L134X: kept from MSPM0L11XX_L13XX_DFP 1.3.1, dropped MSPM0L_DFP 1.2.1

The drops are listed in manifest.json under "issues". Note that ti-lprf-pacs ships both cc13x2_26x2.svd and cc13x2_cc26x2.svd. They differ in content (different generator runs upstream), so both are kept as-is.

## LICENSE AND REDISTRIBUTION STATUS

Copies of every license file retrieved are in LICENSES/.

TI CMSIS packs (MSPM0, MSPM33, MSPS003, MSP432): each pack ships a license file with the standard BSD-3-Clause text. There are four minor textual variants (copyright years, whitespace), all with the same clauses. From TexasInstruments.MSPM0G1X0X_G3X0X_DFP:

> Copyright (c) 2023, Texas Instruments Incorporated
> All rights reserved.
>
> Redistribution and use in source and binary forms, with or without
> modification, are permitted provided that the following conditions
> are met: [...]
> * Neither the name of Texas Instruments Incorporated nor the names of
> its contributors may be used to endorse or promote products derived
> from this software without specific prior written permission.

Redistribution of these files is permitted under those conditions.

Keil.TM4C_DFP: unclear (Keil pack, no license element). The pdsc has no license element and the pack contains no license file. Verified by inspecting Keil.TM4C_DFP.pdsc inside the 1.1.0 pack. Treat redistribution of the TM4C files as unreviewed; check with Arm/Keil before publishing them.

ti-simplelink-pacs: repo LICENSE is BSD-3-Clause text, "Copyright (c) 2024-2026, Texas Instruments Incorporated". Redistribution permitted under the BSD conditions.

ti-lprf-pacs: repo LICENSE is BSD-3-Clause text, "Copyright 2023 Sean Lyons". Caveat: these SVDs were generated from TI Code Composer Studio targetdb data. TI's CCS data license ("for use only with TI Devices") may apply to the underlying data even though the repo is BSD-3-Clause. Flagged for legal review before any public redistribution.

## Provenance legend

- pristine: taken unmodified from a vendor pack or official vendor repo
- patched: vendor file with local fixes (none in this collection)
- community: third-party generated, not vendor reviewed (the CC13xx/CC26xx families, see the coverage table)
- converted: produced by format conversion (none in this collection)

## Refresh

```
python fetch.py
```

Python 3 stdlib plus git on PATH. The script downloads the pack index, compares pack versions and repo HEAD SHAs against manifest.json, re-downloads and re-extracts only the changed sources (cached in .work/ if you pass --keep-work), replaces the affected family files, validates every new file with xml.etree (root element must be device), and updates manifest.json. If nothing changed it prints "up to date" and exits without touching anything. Deleting manifest.json forces a full rebuild. Pack versions move when TI publishes updates, so file counts can change.

The fetch is incremental: it checks upstream versions first and downloads only what changed. A GitHub Action runs it weekly (Monday 06:00 UTC) and commits any updates.

## Known gaps

- Sitara AM2x (AM243x etc.): no SVD files exist anywhere, TI does not publish them.
- CC13xx/CC26xx (pre CC23x0): no official vendor SVDs, community files only. The CC26x0 family (CC2650, CC2640, CC2630) comes from cmsis-svd-data, community provenance with no explicit license on the file.
- CC2538 and the CC3xxx Wi-Fi parts (CC3200/CC3220/CC3235): no SVD exists anywhere, official or community.
- C2000, MSP430: not Arm cores, no SVD.
- TM4C pack is from 2016 and Keil-authored; TI never published its own Tiva-C SVDs.
