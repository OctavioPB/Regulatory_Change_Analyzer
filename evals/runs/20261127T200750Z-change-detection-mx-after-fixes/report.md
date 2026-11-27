# Change detection — 20261127T200750Z-change-detection-mx-after-fixes

- Real amendments: SEC rules from the eCFR and Mexican federal laws from the DOF (16 fixtures), graded by code.
- Code: commit 9bb670a + uncommitted changes

## Summary

| metric | all | MX | US |
|---|---|---|---|
| pass | 16/16 | 7/7 | 9/9 |
| changes_detected | 12/12 | 5/5 | 7/7 |
| controls_quiet | 4/4 | 2/2 | 2/2 |
| facts_found | 20/20 | 7/7 | 13/13 |
| change_type_acceptable | 12/12 | 5/5 | 7/7 |
| avg_unit_recall | 0.97 | 1.0 | 0.96 |
| avg_unit_precision | 1.0 | 1.0 | 1.0 |
| avg_flagged_share | 0.45 | 0.02 | 0.76 |
| avg_truly_changed_share | 0.36 | 0.02 | 0.61 |
| versions_paired_by_title | 16/16 | 7/7 | 9/9 |

## Cases

| case | citation | pass | detected | facts | types (expected) | units R / P (flagged) | text flagged / truly changed | regulation_key |
|---|---|---|---|---|---|---|---|---|
| control-reissue-2022 | 17 CFR 275.206(4)-1 | ✓ | False | 0/0 | — (none) | None / None (0) | 0.000 / 0.000 | cfr:17:275.206(4)-1 |
| control-stable-15c6-1 | 17 CFR 240.15c6-1 | ✓ | False | 0/0 | — (none) | None / None (0) | 0.000 / 0.000 | cfr:17:240.15c6-1 |
| electronic-records-2023 | 17 CFR 240.17a-4 | ✓ | True | 2/2 | new_requirement, other (new_requirement) | 1.0 / 1.0 (4) | 0.476 / 0.292 | cfr:17:240.17a-4 |
| marketing-rule-2021 | 17 CFR 275.206(4)-1 | ✓ | True | 3/3 | new_requirement, other (new_requirement) | 1.0 / 1.0 (6) | 1.000 / 0.932 | cfr:17:275.206(4)-1 |
| names-rule-2023 | 17 CFR 270.35d-1 | ✓ | True | 1/1 | limit_modification, new_requirement, other (new_requirement) | 0.7 / 1.0 (7) | 0.997 / 0.784 | cfr:17:270.35d-1 |
| rule-10b5-1-2023 | 17 CFR 240.10b5-1 | ✓ | True | 1/1 | new_requirement, other (deadline, new_requirement) | 1.0 / 1.0 (4) | 1.000 / 0.787 | cfr:17:240.10b5-1 |
| schedule-13d-2024 | 17 CFR 240.13d-1 | ✓ | True | 2/2 | deadline, other (deadline) | 1.0 / 1.0 (9) | 0.850 / 0.486 | cfr:17:240.13d-1 |
| tplus1-2023 | 17 CFR 240.15c6-1 | ✓ | True | 3/3 | deadline, other (deadline, limit_modification) | 1.0 / 1.0 (3) | 0.761 / 0.760 | cfr:17:240.15c6-1 |
| tplus2-2017 | 17 CFR 240.15c6-1 | ✓ | True | 1/1 | deadline (deadline, limit_modification) | 1.0 / 1.0 (1) | 0.202 / 0.202 | cfr:17:240.15c6-1 |
| mx-cff-improcedencia-2025 | CFF — DOF 16oct25 | ✓ | True | 1/1 | new_requirement (new_requirement) | 1.0 / 1.0 (1) | 0.002 / 0.002 | law:codigo fiscal de la federacion |
| mx-control-lgoaac-2024a | LGOAAC (no reform) | ✓ | False | 0/0 | — (none) | None / None (0) | 0.000 / 0.000 | law:ley general de organizaciones y actividades auxiliares del credito |
| mx-control-lgoaac-2024b | LGOAAC (no reform) | ✓ | False | 0/0 | — (none) | None / None (0) | 0.000 / 0.000 | law:ley general de organizaciones y actividades auxiliares del credito |
| mx-lgoaac-almacenes-2024 | LGOAAC — DOF 26mar24 | ✓ | True | 2/2 | deadline, new_requirement, other (new_requirement) | 1.0 / 1.0 (12) | 0.078 / 0.079 | law:ley general de organizaciones y actividades auxiliares del credito |
| mx-lic-procedimiento-2024 | LIC — DOF 24ene24 | ✓ | True | 2/2 | new_requirement, other (clarification, new_requirement) | 1.0 / 1.0 (3) | 0.015 / 0.015 | law:ley de instituciones de credito |
| mx-lmv-homologacion-2025 | LMV — DOF 14nov25 | ✓ | True | 1/1 | other (clarification, other) | 1.0 / 1.0 (1) | 0.002 / 0.002 | law:ley del mercado de valores |
| mx-lritf-homologacion-2025 | LRITF — DOF 14nov25 | ✓ | True | 1/1 | other (clarification, other) | 1.0 / 1.0 (1) | 0.005 / 0.005 | law:ley para regular las instituciones de tecnologia financiera |

*units* = paragraphs (CFR) or articles (Mexican laws) the app flags, against those that really changed: R = recall, P = precision. *text flagged* = share of the document the app reports as changed (what a reviewer must read).
