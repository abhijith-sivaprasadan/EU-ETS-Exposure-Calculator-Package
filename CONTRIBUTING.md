# Contributing

Issues and pull requests are welcome. Keep regulatory assumptions, data vintages, units, and calculation boundaries explicit. Add tests for every calculation change and update the documentation when policy inputs or outputs change.

Before submitting, run `ruff check .`, `black --check .`, and `python -m pytest -q`. Never commit credentials, client data, or licensed datasets that cannot be redistributed.
