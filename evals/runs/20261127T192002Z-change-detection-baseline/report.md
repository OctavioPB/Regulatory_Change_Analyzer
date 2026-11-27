# Change detection — 20261127T192002Z-change-detection-baseline

- Real SEC amendments from the eCFR (9 fixtures), graded by code.
- Code: commit db55ea1 + uncommitted changes

## Summary

| metric | value |
|---|---|
| pass | 7/9 |
| changes_detected | 6/7 |
| controls_quiet | 2/2 |
| facts_found | 12/13 |
| change_type_acceptable | 5/7 |
| localized_below_section | 0/7 |
| avg_flagged_share | 0.86 |
| avg_truly_changed_share | 0.61 |
| versions_paired_by_title | 0/9 |

## Cases

| case | citation | pass | detected | facts | types (expected) | flagged / truly changed | regulation_key |
|---|---|---|---|---|---|---|---|
| control-reissue-2022 | 17 CFR 275.206(4)-1 | ✓ | False | 0/0 | — (none) | 0.00 / 0.00 | None |
| control-stable-15c6-1 | 17 CFR 240.15c6-1 | ✓ | False | 0/0 | — (none) | 0.00 / 0.00 | None |
| electronic-records-2023 | 17 CFR 240.17a-4 | ✓ | True | 2/2 | new_requirement (new_requirement) | 1.00 / 0.29 | None |
| marketing-rule-2021 | 17 CFR 275.206(4)-1 | ✓ | True | 3/3 | new_requirement (new_requirement) | 1.00 / 0.93 | None |
| names-rule-2023 | 17 CFR 270.35d-1 | ✓ | True | 1/1 | new_requirement (new_requirement) | 1.00 / 0.78 | None |
| rule-10b5-1-2023 | 17 CFR 240.10b5-1 | ✓ | True | 1/1 | new_requirement (deadline, new_requirement) | 1.00 / 0.79 | None |
| schedule-13d-2024 | 17 CFR 240.13d-1 | ✗ | True | 2/2 | new_requirement (deadline) | 1.00 / 0.49 | None |
| tplus1-2023 | 17 CFR 240.15c6-1 | ✓ | True | 3/3 | limit_modification (deadline, limit_modification) | 1.00 / 0.76 | None |
| tplus2-2017 | 17 CFR 240.15c6-1 | ✗ | False | 0/1 | — (deadline, limit_modification) | 0.00 / 0.20 | None |

*flagged* = share of the section the app reports as changed (what a reviewer must read); *truly changed* = share of paragraphs that changed, by official label.
