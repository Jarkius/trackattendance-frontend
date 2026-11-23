# 06: Roster header normalisation, and every import abort is surfaced (#105)

## Objective
A roster with cosmetic header differences imports correctly. Any condition that prevents an import reaches the operator as a roster error.

## Dependencies
- none

## Scope
- Relevant modules/files: `attendance.py` (`validate_roster_headers` :69, `_bootstrap_employee_directory` :113-245)
- Expected behavior:
  - Validation and import share one header normalisation: strip whitespace including NBSP, and match case-insensitively onto the canonical names in `REQUIRED_COLUMNS`.
  - Missing columns, a strict-validation skip, and "0 valid rows" raise `ValueError` with an operator-readable message, which `__init__` stores as `_roster_error`.

## Acceptance Criteria
- [ ] Given the headers `"Legacy ID "`, `"legacy id"` or `"Legacy ID"`, then the roster imports and the badge matches.
- [ ] Given a required column is truly missing, then `_roster_error` names it. If a previous roster exists, it is left in place and the error still shows.
- [ ] Given a header row with no valid data rows, then `_roster_error` is set.
- [ ] Turn the reproduction cases from #105 into tests.

## Contracts and Constraints
- Keep the existing duplicate-Legacy-ID `ValueError` behavior.
- Non-goal: changing the Legacy ID value itself (that is ticket 07).

## Verification
```bash
python -m pytest tests/test_roster_bootstrap_corrupt_file.py tests/test_config.py -v
python -m pytest tests/ <CI ignores> -v --tb=short
```

## Completion Report
- Changed files:
- Verification results:
- Known limitations:
