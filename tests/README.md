# Tests

This directory contains test scripts for verifying cmdseal functionality.

## Running Tests

### GUI Wizard Tests
```bash
QT_QPA_PLATFORM=offscreen uv run python tests/test_wizard_simplification.py
```

### Smoke Test
```bash
make smoke
```

## Test Files

- `test_wizard_simplification.py` - Tests for GUI wizard simplification features:
  - Literal password support (without `{{secret:}}`)
  - SecretsPage auto-skip when no secrets present
  - Bare placeholder warning detection

## Notes

- All GUI tests require `QT_QPA_PLATFORM=offscreen` for headless testing
- Use `uv run python` instead of `python3` to ensure PySide6 is available
- Tests are designed to be non-interactive and CI-friendly
