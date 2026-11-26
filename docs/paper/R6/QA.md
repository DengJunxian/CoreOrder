# R6 manuscript verification

26 November 2026, Asia/Shanghai. Evidence baseline `a58c37842b0bc3583410bbf24f8eb7ca9fb29877`. Tested production source `58ec5764c21833142c50abacd9e2302404ffdb06`.

| Check | Result |
| --- | --- |
| Document build | PASS. Typst 0.15.1 compiled the 10-page main paper and 4-page supplement on A4 with exit 0. Compiling both into a new directory with the documented creation timestamp produced byte-identical PDFs. |
| Visual and text review | PASS. Rendered all 14 pages with Poppler and inspected the cover, figures, formulas, tables, section flow and references. Checked the FCN expression against the pinned source and the paired estimator against the candidate protocol and report implementation. |
| Correctness and identity | PASS. Matched the 565 validation records, five seeds per suite, and all 12 seed-101 anchors. The W3 AoS direct and 1/2/4 worker receipts point to one independent oracle. The three pinned gitlinks and version declarations match the tested source. |
| Campaign audit | PASS. Rechecked 569 unrun entries including 70 warmups, with 19 comparisons and 285 missing pair positions. All entries have zero qualified observations, so the article contains no estimates of formal speedup or confidence intervals. |
| Numeric and figure lineage | PASS. Recomputed heap comparator totals, validated replay directions, output digests and units, and checked P11 timings and inclusive spans. Rebuilt the R5B derived evidence and compared it byte-for-byte. Checked all embedded figure paths and all 18 claim-ledger rows. |
| Bibliography | PASS. The 14 cited keys match the bibliography and individual audit. Checked editions, authors, venue or source version, year, publication identifiers and the supported claim. |
| Remaining research input | BLOCKED. G3 formal approval is still required. Formal x86 timing and E05 remained NOT_RUN at the R5B cutoff. |

This is a manuscript build and evidence audit. It reused the recorded x86 Release build and correctness evidence. The manuscript stage ran no new market timing campaign.
