# Change detection — 20261127T200349Z-change-detection-baseline-strict

- Real amendments: SEC rules from the eCFR and Mexican federal laws from the DOF (16 fixtures), graded by code.
- Code: commit 9bb670a + uncommitted changes

## Summary

| metric | all | MX | US |
|---|---|---|---|
| pass | 11/16 | 2/7 | 9/9 |
| changes_detected | 12/12 | 5/5 | 7/7 |
| controls_quiet | 4/4 | 2/2 | 2/2 |
| facts_found | 20/20 | 7/7 | 13/13 |
| change_type_acceptable | 9/12 | 2/5 | 7/7 |
| avg_unit_recall | 0.84 | 0.68 | 0.96 |
| avg_unit_precision | 0.68 | 0.22 | 1.0 |
| avg_flagged_share | 0.59 | 0.37 | 0.76 |
| avg_truly_changed_share | 0.36 | 0.02 | 0.61 |
| versions_paired_by_title | 9/16 | 0/7 | 9/9 |

## Cases

| case | citation | pass | detected | facts | types (expected) | units R / P (flagged) | text flagged / truly changed | regulation_key |
|---|---|---|---|---|---|---|---|---|
| control-reissue-2022 | 17 CFR 275.206(4)-1 | ✓ | False | 0/0 | — (none) | None / None (0) | 0.000 / 0.000 | cfr:17:275.206(4)-1 |
| control-stable-15c6-1 | 17 CFR 240.15c6-1 | ✓ | False | 0/0 | — (none) | None / None (0) | 0.000 / 0.000 | cfr:17:240.15c6-1 |
| electronic-records-2023 | 17 CFR 240.17a-4 | ✓ | True | 2/2 | new_requirement (new_requirement) | 1.0 / 1.0 (4) | 0.476 / 0.292 | cfr:17:240.17a-4 |
| marketing-rule-2021 | 17 CFR 275.206(4)-1 | ✓ | True | 3/3 | new_requirement, other (new_requirement) | 1.0 / 1.0 (6) | 1.000 / 0.932 | cfr:17:275.206(4)-1 |
| names-rule-2023 | 17 CFR 270.35d-1 | ✓ | True | 1/1 | limit_modification, new_requirement, other (new_requirement) | 0.7 / 1.0 (7) | 0.997 / 0.784 | cfr:17:270.35d-1 |
| rule-10b5-1-2023 | 17 CFR 240.10b5-1 | ✓ | True | 1/1 | new_requirement, other (deadline, new_requirement) | 1.0 / 1.0 (4) | 1.000 / 0.787 | cfr:17:240.10b5-1 |
| schedule-13d-2024 | 17 CFR 240.13d-1 | ✓ | True | 2/2 | deadline, other (deadline) | 1.0 / 1.0 (9) | 0.850 / 0.486 | cfr:17:240.13d-1 |
| tplus1-2023 | 17 CFR 240.15c6-1 | ✓ | True | 3/3 | deadline, limit_modification (deadline, limit_modification) | 1.0 / 1.0 (3) | 0.761 / 0.760 | cfr:17:240.15c6-1 |
| tplus2-2017 | 17 CFR 240.15c6-1 | ✓ | True | 1/1 | deadline (deadline, limit_modification) | 1.0 / 1.0 (1) | 0.202 / 0.202 | cfr:17:240.15c6-1 |
| mx-cff-improcedencia-2025 | CFF — DOF 16oct25 | ✗ | True | 1/1 | clarification, deadline, limit_modification, new_requirement, other, repeal (new_requirement) | 1.0 / 0.01 (100) | 0.289 / 0.002 | None |
| mx-control-lgoaac-2024a | LGOAAC (no reform) | ✓ | False | 0/0 | — (none) | None / None (0) | 0.000 / 0.000 | None |
| mx-control-lgoaac-2024b | LGOAAC (no reform) | ✓ | False | 0/0 | — (none) | None / None (0) | 0.000 / 0.000 | None |
| mx-lgoaac-almacenes-2024 | LGOAAC — DOF 26mar24 | ✗ | True | 2/2 | deadline, new_requirement, other, repeal (new_requirement) | 0.42 / 0.08 (64) | 0.892 / 0.079 | None |
| mx-lic-procedimiento-2024 | LIC — DOF 24ene24 | ✗ | True | 2/2 | clarification, deadline, limit_modification, new_requirement, other, repeal (clarification, new_requirement) | 0.0 / 0.0 (173) | 0.526 / 0.015 | None |
| mx-lmv-homologacion-2025 | LMV — DOF 14nov25 | ✗ | True | 1/1 | deadline, new_requirement, other, repeal (clarification, other) | 1.0 / 0.03 (32) | 0.120 / 0.002 | None |
| mx-lritf-homologacion-2025 | LRITF — DOF 14nov25 | ✗ | True | 1/1 | deadline (clarification, other) | 1.0 / 1.0 (1) | 0.005 / 0.005 | None |

*units* = paragraphs (CFR) or articles (Mexican laws) the app flags, against those that really changed: R = recall, P = precision. *text flagged* = share of the document the app reports as changed (what a reviewer must read).
