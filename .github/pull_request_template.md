## What & why

<!-- One or two sentences: the problem and the change. Link the issue if there is one. -->

## How it was tested

- [ ] `python -m pytest` (unit)
- [ ] `python -m pytest -m integration` against a `*_test` database, if DB/HTTP code changed
- [ ] `cd frontend && npm test && npm run build`, if the UI changed

## Checklist

- [ ] New API routes declare a `Require*` role dependency
- [ ] Schema changes come with an Alembic migration in `alembic/versions/`
- [ ] No secrets, `.env` values or personal data in the diff
