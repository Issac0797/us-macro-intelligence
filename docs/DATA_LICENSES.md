# Independent data permission register

Review date: **2026-11-18**. Machine-readable, fail-closed authority: [licenses.json](../data/licenses.json). Schema: [snapshot.schema.json](../data/snapshot.schema.json). The project MIT license does not relicense any third-party data or source extract.

| Aliases | Original native source | Permission result | Public release |
| --- | --- | --- | --- |
| CPIAUCSL, CPILFESL | BLS CUSR0000SA0, CUSR0000SA0L1E | PASS — agency public-domain statistical material; attribution retained | Included |
| UNRATE, PAYEMS | BLS LNS14000000, CES0000000001 | PASS — same BLS policy | Included |
| DGS1MO, DGS3MO, DGS6MO, DGS1, DGS2, DGS5, DGS10, DGS30 | Board H.15 nominal constant-maturity `RIFLGFC*` daily series | PASS — Board public-domain information policy; attribution retained | Included |
| DFF | Board H.15 `RIFSPFF_N.D`, calendar-daily effective federal funds rate | PASS — same Board policy; actual, not target rate | Included |
| Five selected historical Fed target ranges | Source-linked Board statements dated 2020-03-15, 2022-03-16, 2023-07-26, 2024-09-18, 2026-10-28 | PASS — only factual dates/ranges and source links exported | Included, explicitly incomplete |
| PCEPI, PCEPILFE, GDPC1, CES0500000003, JTSJOL, RSAFS, INDPRO | Not approved for this export | BLOCKED for export — this release has not completed per-series review | Excluded |
| NBER, recession overlays, ALFRED vintages, all other series | Not approved for this export | BLOCKED for export | Excluded |
| Database dumps, logs, personal annotations/workspaces, raw downloaded HTML/XML ZIP | Private/internal or outside whitelist scope | BLOCKED for export | Excluded |

**BLS:** [Linking and Copyright Information](https://www.bls.gov/bls/linksite.htm) identifies its published material as public domain except previously copyrighted photos/illustrations, and requests source citation. This release uses statistical values only, no imagery or emblem.

**Federal Reserve Board:** [Disclaimer — Copyright/trademark](https://www.federalreserve.gov/disclaimer.htm) allows copying/distributing Board information unless otherwise indicated and requests attribution. Third-party content and seals/logos require separate treatment and are excluded. The official [H.15 XML](https://www.federalreserve.gov/releases/h15/data/FRB_h15_xml.zip) is the direct numeric source; no FRED download or FRED chart is repackaged. The Board's [H.15 page](https://www.federalreserve.gov/releases/h15/) provides definitions and methodology links. Source HTML test fixtures are limited to public Board text/structure for regression testing; their agency content retains its own status and is not MIT-licensed project prose.

**FRED/ALFRED:** [FRED terms](https://fred.stlouisfed.org/legal/) distinguish ownership and permitted uses. Being readable, downloadable or referenced by an ID is not redistribution permission. The full local terminal can retrieve FRED for its operator's own authorized use; those downloads are not part of this public repository or deployment.

Each series includes real observation dates, values/nulls, native unit, frequency, seasonal adjustment, original source URL, download URL, generation timestamp, actual coverage bounds/count, policy reference, attribution and review date. The top-level object records original response checksums and the distinction between a latest-revised snapshot and historical vintages. Monthly dates are statistical period labels, not exact release days.

Permission review must precede any new series addition. Unlisted/unknown series cannot be exported. Recheck source policies when refreshing; retain notices and source links in both JSON and visible charts/source pages. Do not add datasets to the MIT grant, remove limitations, use official marks, or imply government endorsement. A commercial redistribution or a new data provider needs its own terms review.
