# Change detection — 20261127T192535Z-change-detection-after-fixes

- Real SEC amendments from the eCFR (9 fixtures), graded by code.
- Code: commit db55ea1 + uncommitted changes

## Summary

| metric | value |
|---|---|
| pass | 9/9 |
| changes_detected | 7/7 |
| controls_quiet | 2/2 |
| facts_found | 13/13 |
| change_type_acceptable | 7/7 |
| localized_below_section | 7/7 |
| avg_flagged_share | 0.76 |
| avg_truly_changed_share | 0.61 |
| versions_paired_by_title | 9/9 |

## Cases

| case | citation | pass | detected | facts | types (expected) | flagged / truly changed | regulation_key |
|---|---|---|---|---|---|---|---|
| control-reissue-2022 | 17 CFR 275.206(4)-1 | ✓ | False | 0/0 | — (none) | 0.00 / 0.00 | cfr:17:275.206(4)-1 |
| control-stable-15c6-1 | 17 CFR 240.15c6-1 | ✓ | False | 0/0 | — (none) | 0.00 / 0.00 | cfr:17:240.15c6-1 |
| electronic-records-2023 | 17 CFR 240.17a-4 | ✓ | True | 2/2 | new_requirement (new_requirement) | 0.48 / 0.29 | cfr:17:240.17a-4 |
| marketing-rule-2021 | 17 CFR 275.206(4)-1 | ✓ | True | 3/3 | new_requirement, other (new_requirement) | 1.00 / 0.93 | cfr:17:275.206(4)-1 |
| names-rule-2023 | 17 CFR 270.35d-1 | ✓ | True | 1/1 | limit_modification, new_requirement, other (new_requirement) | 1.00 / 0.78 | cfr:17:270.35d-1 |
| rule-10b5-1-2023 | 17 CFR 240.10b5-1 | ✓ | True | 1/1 | new_requirement, other (deadline, new_requirement) | 1.00 / 0.79 | cfr:17:240.10b5-1 |
| schedule-13d-2024 | 17 CFR 240.13d-1 | ✓ | True | 2/2 | deadline, other (deadline) | 0.85 / 0.49 | cfr:17:240.13d-1 |
| tplus1-2023 | 17 CFR 240.15c6-1 | ✓ | True | 3/3 | deadline, limit_modification (deadline, limit_modification) | 0.76 / 0.76 | cfr:17:240.15c6-1 |
| tplus2-2017 | 17 CFR 240.15c6-1 | ✓ | True | 1/1 | deadline (deadline, limit_modification) | 0.20 / 0.20 | cfr:17:240.15c6-1 |

*flagged* = share of the section the app reports as changed (what a reviewer must read); *truly changed* = share of paragraphs that changed, by official label.
