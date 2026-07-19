# PLAN — ScreenTranslator

## Next actions

1. **Commit the 2026-06-26 working-tree batch.** ~545 insertions across 8 files plus the untracked `tests/` folder (config self-repair + atomic save, GUI/preview rework, overlay fixes, torch-before-winocr import-order fix, Ollama URL normalization, requirements cleanup). Run `python tests/test_pure_functions.py` first; split into logical commits if convenient, one big `feat:` commit is acceptable.
2. **Reconcile the default OCR engine.** `config.DEFAULT_CONFIG` says `WindowsOCR`, the live `config.json` uses `EasyOCR` with `multi_ocr: true`. Decide which default a fresh install should get and record it in DECISIONS.md.
3. **Verify the conda env still matches `requirements.txt`** (torch + easyocr + winocr coexistence is fragile; see the import-order note in `ocr.py`).

## Roadmap (rough)

- Packaging for one-click launch (PyInstaller or a Start-Menu shortcut into the conda env) — currently launched by hand with `python main.py`. TODO(edgar): decide if this is wanted.
- Trim or split optional heavy OCR deps (paddlepaddle/paddleocr/manga-ocr) out of the default install path.

## Open questions

- TODO(edgar): is this project actively used day-to-day (the June captures suggest yes)? If yes, does the recapture-area workflow need a multi-region preset list?
- TODO(edgar): should `source/` and `translated/` get an automatic cleanup/retention policy? They accumulate ~60 MB of PNGs already (all under 2 MB each, so nothing trips the 50 MB per-file gitignore rule).
