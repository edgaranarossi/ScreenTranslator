# DECISIONS — ScreenTranslator

Dated log: decision, alternatives considered, reason. Newest first.

## 2026-07-19 — Doc-set backfill & structure conformance

- Backfilled the constitution doc set (README status line, PLAN.md, DECISIONS.md, WISHLIST.md) with no code changes. The repo was already gitified (2026-05-20, remote `github.com/edgaranarossi/ScreenTranslator`), so gitification was not needed.
- Extended `.gitignore` with test caches and generated-data folders; no files over 50 MB exist; no secrets found (translation is local-Ollama only, so there is no `.env` / `.env.example` — nothing to hold).
- Entries below 2026-07-19 are reconstructed from git history and code comments only; anything not certain is left out.

## Uncommitted (working tree, file dates 2026-06-26) — not yet in git history

Certain from the code itself, awaiting commit (see PLAN.md #1):

- **torch must import before winocr** (`ocr.py` header comment): winocr's WinRT runtime loads C++/OpenMP DLLs that break torch's `c10.dll` init (WinError 1114) if torch comes second; torch is pre-imported at module load to fix every engine combination.
- **`config.json` is self-repairing and atomically written** (`config.py`): missing keys seeded, empty strings and type drift repaired against `DEFAULT_CONFIG`; corrupt files are renamed aside (`config.json.bad-*`) instead of destroyed; saves go through tmp-file + fsync + `os.replace`.
- **Ollama URL normalization** (`translator.py`): user-configured base URLs are normalized to the `/api/chat` endpoint because the payload uses chat-style `messages` (base URL alone returned 405).
- **Pure-function regression tests** (`tests/test_pure_functions.py`): runnable standalone or via pytest, covering URL normalization, color conversion, CJK detection, text wrapping, font coverage routing, and config load/repair/atomicity.

## 2026-05-21 — Multi-OCR consensus pipeline (`cf0048a`)

Multiple OCR engines can vote on the same region ("proposals" merged into consensus text); batched translation fallback loop fixed in the same commit. Preceded the same day by distance-based constraints + semantic text-block merging with bounding-box fusion (`228d68a`) and rotated text overlay with variable per-word font color, recorded in the commit message as "Option A" (`44b073e`) — the alternatives A/B/C considered are not recorded. TODO(edgar): note what Options B/C were if it ever matters again.

## 2026-05-20 — Native Windows Media OCR (winocr) as default engine (`25179d3`)

winocr integrated and made the default OCR engine (no torch needed for the default path). `config.DEFAULT_CONFIG` still carries `WindowsOCR` as the default today, while the live `config.json` uses EasyOCR + multi-OCR — see PLAN.md #2.

## 2026-05-20 — Gitified, MIT licensed, README added (`0802802`, `86b1911`)

First commits (`6f1d80a`…) land an already-working app — file dates show the project existed since at least 2026-04-29, pre-git. MIT chosen as the license. README claims were deliberately softened the same day ("docs: simplify README by removing strong claims").

## Undated (from code, certain by design) — local-only translation

Translation runs against a **local Ollama instance** (`http://localhost:11434/api/chat`, default model `aya-expanse:8b`); OCR engines run locally too. No cloud translation APIs, no keys, no telemetry anywhere in the code — the tool works fully offline once models are downloaded. TODO(edgar): the original motivation (privacy vs. cost vs. latency) predates git history and is not recorded.
