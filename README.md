<div align="center">

# CodeShift

**Automated Code Migration System**

Convert code between Python, Java, C and C++ — or upgrade a legacy codebase to a modern
language version — then verify the result actually compiles and behaves the same.

[![CI](https://github.com/thanmai-kolli/automated-code-migration-system/actions/workflows/ci.yml/badge.svg)](https://github.com/thanmai-kolli/automated-code-migration-system/actions/workflows/ci.yml)

</div>

![CodeShift landing page](docs/screenshots/01-landing-hero.png)

---

## What it does

| Engine | Does | Covers |
| --- | --- | --- |
| **Cross-Language** | Parses to a neutral IR, infers types across the whole program, regenerates | all 12 ordered pairs of Python, Java, C, C++ |
| **Version Upgrade** | Detects the version in use and rewrites deprecated constructs | Python → 3.12, Java → 17, C → C17, C++ → C++20 |

Every run returns a **Migration Intelligence Report**: predicted accuracy and
confidence, risk triggers, real compiler output, semantic findings, token/AST/structure
similarity, a unified diff, and timing.

> The translation is **fully deterministic** — parse, lower to IR, type-annotate,
> re-emit. No LLM is involved, so the same input always gives the same output. Machine
> learning only *scores* a finished migration and auto-detects the source language.

---

## Architecture

```
codeshift-frontend/   React 19 + Vite + Monaco   →   3-step workspace
        │  POST /api/*  (proxied by Vite in dev)
        ▼
codeshift-backend/    Flask API
        ├── cross_language_system/   parse → IR → types → generate → validate → score
        └── version_upgrade_system/  detect → transform → validate → risk → score
```

The **type annotator** is what makes statically typed targets work. Python and C carry
almost no type information syntactically, so a three-pass whole-program analysis
resolves every parameter, field, local and return type — from literals, from usage
(`amount > self.balance` ⇒ numeric, `total += s` ⇒ `s` is `total`'s type), from
call-site arguments, and by unifying constructor parameters with the fields they
initialise. Without it every signature degrades to `Object` and nothing compiles.

Parsers: Python via `ast`, Java via `javalang`, C/C++ via a recursive-descent parser.
C ↔ C++ also has a direct text rewriter, which round-trips those two exactly.

Both engines also run as interactive CLIs from `codeshift-backend/`:
`python -m cross_language_system.main_cross` and `python -m version_upgrade_system.main`.

---

## Quick start

**Prerequisites** — Python 3.10+, Node 18+. For compile validation: `javac`, `gcc`, `g++`.

```bash
# backend
cd codeshift-backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python flask_app.py                    # http://127.0.0.1:5000

# frontend, in a second terminal
cd codeshift-frontend
npm install && npm run dev             # http://localhost:5173
```

Vite proxies `/api` to Flask, so no CORS setup is needed.

<details>
<summary>Configuration</summary>

| Variable | Default | Purpose |
| --- | --- | --- |
| `HOST` / `PORT` | `127.0.0.1` / `5000` | bind address |
| `FLASK_DEBUG` | `0` | `1` enables auto-reload |
| `CORS_ORIGINS` | `localhost:5173,127.0.0.1:5173` | origins allowed without the Vite proxy |
| `CODESHIFT_ENABLE_TEST_EXECUTION` | `0` | `1` runs test cases — **executes submitted code locally** |
| `CODESHIFT_TEST_TIMEOUT` | `5` | per-run timeout, seconds |

Frontend overrides live in `codeshift-frontend/.env.example`.

</details>

---

## API

Both endpoints are `POST`, take JSON, and return `{ "success": true, "data": {...} }` or
`{ "success": false, "error": "..." }`. Bodies are capped at 1 MB. `GET /` is a health check.

```jsonc
// POST /api/cross-language
{ "code": "...", "source_language": "python", "target_language": "java",
  "test_cases": "2 3\n===\n5" }          // optional

// POST /api/version-upgrade
{ "code": "print 'hi'", "language": "python" }
```

`data` carries the generated `code` plus `accuracy`, `confidence`, `compile_success`,
`compile_errors`, `semantic_issues`, `risk_level`, `risk_triggers`, `diff_text`, the
three similarity scores, `timeTakenMs`, and `detected_version` for upgrades.

---

## Behavioural test validation

Compiling proves the output is valid; running it proves it is correct. Supply
`test_cases` and the engine runs **both** the original and the migration on the same
stdin and compares their stdout.

```
2 3
===
5
---
10 20
===
30
```

Cases split on `---`, input and expected output on `===`. The `===` half is optional —
without it the migration is compared against the original program, catching regressions
with nothing written by hand.

![Test execution summary](docs/screenshots/10-test-execution.png)

> **This executes submitted code.** It is off unless `CODESHIFT_ENABLE_TEST_EXECUTION=1`.
> Runs are capped at 5 s and 20 cases in a throwaway directory with a minimal
> environment — but that is **not** a sandbox. Local use only.

---

## Scoring models

The two scores are predicted by models fitted on **measured migrations**, not on
hand-written rules. `ml/build_dataset.py` runs a corpus of 40 stdin-driven programs
through the engine to every other language and records what actually happened —
**120 measured migrations across all 12 pairs** in `ml/migration_dataset.csv`.

| Model | Predicts | Type |
| --- | --- | --- |
| `accuracy_model.pkl` | `behaviour_score` — % of inputs reproduced exactly | regressor |
| `confidence_model.pkl` | `P(behaviour preserved)` | classifier |
| `language_model.pkl` | source language, when the caller omits it | classifier |

Evaluated with grouped 5-fold CV — all rows for one program share a fold, so a model
cannot score well by recognising a program it saw in another target language:

| | model | baseline |
| --- | --- | --- |
| accuracy — MAE | **4.78** | 40.03 |
| accuracy — R² | **0.875** | −0.009 |
| confidence — accuracy | **0.975** | 0.725 |
| confidence — ROC AUC | **0.963** | 0.500 |

```bash
cd codeshift-backend
set CODESHIFT_ENABLE_TEST_EXECUTION=1
python -m cross_language_system.ml.build_dataset   # compiles and runs everything
python -m cross_language_system.ml.train_models
```

**Measured engine quality:** 90 of 120 migrations compile and 87 preserve behaviour.
Compilation dominates the feature importances, because on this corpus 87 of the 90 that
compile are also correct.

---

## Screenshots

<table>
<tr>
<td width="50%"><img src="docs/screenshots/05-migration-step1-mode.png" alt="Step 1"><br><sub><b>1.</b> Cross-language or version upgrade</sub></td>
<td width="50%"><img src="docs/screenshots/06-migration-step2-config.png" alt="Step 2"><br><sub><b>2.</b> Any source, any of the other three as target</sub></td>
</tr>
</table>

![Python to Java migration result](docs/screenshots/08-migration-result.png)

<details>
<summary>Version upgrade and landing page</summary>

![Python 2 to 3 upgrade](docs/screenshots/09-version-upgrade-result.png)
![Feature grid](docs/screenshots/03-landing-features.png)

</details>

---

## Tests

```bash
cd codeshift-backend  && pip install pytest && python -m pytest -q   # 142 tests
cd codeshift-frontend && npm run lint && npm run build
```

Covers the version detector and every Python 2 → 3 rule, the AST validator, diff and
change counting, the language registry, similarity scoring, all API routes including the
payload limit, the test executor, the scoring models and their dataset, and conversion
fidelity — parser coverage, type inference, generated-code content, and a compile check
on all 12 pairs. Both suites run in CI on every push.

---

## Repository layout

```
codeshift-backend/
  flask_app.py                app factory + health route
  api/                        route blueprints
  tests/                      pytest suite
  cross_language_system/
    core/                     dispatcher, IR, type annotator, test executor, scoring
    parsers/ generators/ validators/     one module per language
    ml/                       corpus, dataset builder, training, models
  version_upgrade_system/
    languages/{python,java,c,cpp}/enterprise_engine/
                              per-language transformer, validator, risk analyzer

codeshift-frontend/src/       pages, components, services, utils, styles
```

---

## Known limitations

- The C/C++ parser covers the common procedural subset. Templates, macros, multiple
  inheritance and pointer arithmetic are not modelled.
- Where a Python type cannot be inferred, the target falls back to `Object` (Java), a
  `template` parameter (C++) or `int` (C, which has no generics). Every such decision is
  reported in the semantic findings.
- Python → C is the weakest direction: C has no strings, growable lists or exceptions, so
  arrays get a companion `_length` variable and `try` blocks are inlined.
- The version-upgrade engine covers a curated rule set per language, not the full
  2to3 / JDK migration surface.
- The corpus is 40 programs; the measured numbers describe that corpus, not all code.
