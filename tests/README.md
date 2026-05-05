# Tests

This directory contains test scripts for verifying cmdseal functionality.

## Running Tests

### Pipe serialization unit tests (v1.2, CI-friendly)
```bash
python3 tests/test_pipe_serialize.py
```
Pure-Python, no keychain / codesign required. Verifies `serialize_segments`
byte layout, single-segment byte-compat with v1.1, and `\x03` separator
insertion for multi-segment pipelines.

### edit-template unit tests (v1.2.1, CI-friendly)
```bash
python3 tests/test_edit_template.py
```
Pure-Python, mocks `kc_list` / `do_seal`. Covers 6 error paths (service not
found, legacy item, invalid comment JSON, missing `output_path`, secret-set
mismatch, too many pipe segments) plus the happy path (correct field
injection + `old_service_to_delete` routing to `do_seal`).

### Pipe end-to-end (v1.2, interactive)
```bash
bash tests/test_v12_pipe_e2e.sh
```
Covers 7 cases: single-segment fast path, 2/3-segment pipelines, cross-segment
`{{arg:N}}`, and the exit-code matrix (upstream-fail / downstream-fail /
leftmost-wins). ⚠️ Each sealed binary triggers a macOS keychain authorization
prompt on first run — click "Always Allow" for each. The script cleans up
sealed binaries and keychain items on exit.

### GUI Wizard Tests
```bash
QT_QPA_PLATFORM=offscreen uv run python tests/test_wizard_simplification.py
```

### Smoke Test
```bash
make smoke
```

## Test Files

- `test_pipe_serialize.py` - v1.2 pipe plaintext-serialization unit tests
  (`serialize_segments`, `tokenize_command`, byte-level v1.1 compatibility).
- `test_edit_template.py` - v1.2.1 `do_edit_template` error-path + happy-path
  regression (6 `sys.exit` branches + correct delegation to `do_seal` with
  `old_service_to_delete`).
- `test_v12_pipe_e2e.sh` - v1.2 pipe end-to-end verification (seal + run +
  exit-code matrix). Interactive: requires keychain authorization per case.
- `test_v11_e2e.sh` - v1.1 end-to-end security validation (hardened runtime,
  `DYLD_*` injection defense, steady-state performance).
- `test_wizard_simplification.py` - Tests for GUI wizard simplification features:
  - Literal password support (without `{{secret:}}`)
  - SecretsPage auto-skip when no secrets present
  - Bare placeholder warning detection

## Notes

- All GUI tests require `QT_QPA_PLATFORM=offscreen` for headless testing
- Use `uv run python` instead of `python3` to ensure PySide6 is available
- Tests are designed to be non-interactive and CI-friendly, except the
  `*_e2e.sh` scripts which require manual keychain authorization
