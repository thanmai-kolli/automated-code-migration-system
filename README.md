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
| **Version Upgrade** | Detects the version in use and applies rewrite rules, keeping each one only if the program still compiles (and passes your tests) | Python → 3.12, Java → 17, C → C17, C++ → C++20 |

Every run returns a **Migration Intelligence Report**: predicted accuracy and
confidence, risk triggers, real compiler output, semantic findings, token/AST/structure
similarity, a unified diff, and timing.

> The translation is **fully deterministic** — parse, lower to IR, type-annotate,
> re-emit. No LLM is involved, so the same input always gives the same output. Machine
> learning only *scores* a finished migration and auto-detects the source language.
> A construct that cannot be translated faithfully is **refused with an explanation**
> instead of being approximated.

---

## Architecture

```
codeshift-frontend/   React 19 + Vite + Monaco   →   3-step workspace
        │  POST /api/*  (proxied by Vite in dev)
        ▼
codeshift-backend/    Flask API
        ├── cross_language_system/   parse → IR → types → generate → validate → score
        └── version_upgrade_system/  detect → candidate rules → compile/test gate per rule → report
```

The **type annotator** is what makes statically typed targets work. Python and C carry
almost no type information syntactically, so a three-pass whole-program analysis
resolves every parameter, field, local and return type — from literals, from usage
(`amount > self.balance` ⇒ numeric, `total += s` ⇒ `s` is `total`'s type), from
call-site arguments, and by unifying constructor parameters with the fields they
initialise. Without it every signature degrades to `Object` and nothing compiles.

The type annotator also fixes the source language's arithmetic: integer `/` and `%`
truncate for C and Java sources and floor for Python sources, and implicit int/double
conversions become explicit casts, so every target computes the same numbers.

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

The scores are predicted by models fitted on **measured migrations**, not on
hand-written rules. `ml/build_dataset.py` translates every program of `ml/corpus.py` and
`ml/corpus_extra.json` into the other three languages, compiles and runs both sides on
the programs' inputs, and records what actually happened — **297 measured translations
of 46 tasks** in `ml/migration_dataset.csv` (refused translations are excluded).

| Model | Predicts | Type |
| --- | --- | --- |
| `confidence_model.pkl` | `P(behaviour preserved)` | logistic regression on 4 features |
| `accuracy_model.pkl` | `behaviour_score`, shown as predicted accuracy | 100 × the same probability |
| `language_model.pkl` | source language, when the caller omits it | TF-IDF + logistic regression |

`train_models.py` compares logistic regression, a random forest and a calibrated random
forest on all 25 features and on a 4-feature subset with grouped 5-fold CV — all rows for
one program share a fold — and deploys the lowest Brier score. Results are written to
`ml/model_card.json`:

| grouped CV | deployed | compile status only | prior / mean |
| --- | --- | --- | --- |
| confidence — Brier score | **0.016** | 0.023 | 0.069 |
| confidence — ROC AUC | **0.958** | 0.810 | n/a |
| accuracy — MAE (points) | **3.88** | 4.61 | 13.78 |

```bash
cd codeshift-backend
set CODESHIFT_ENABLE_TEST_EXECUTION=1
python -m cross_language_system.ml.build_dataset      # compiles and runs everything
python -m cross_language_system.ml.train_models
python -m cross_language_system.ml.language_detector  # grouped CV, then saves the model
```

When test cases are supplied, the report shows the **measured** accuracy (share of passed
test cases) instead of the predicted one, next to the model's confidence.

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
cd codeshift-backend  && pip install pytest && python -m pytest -q   # 228 tests
cd codeshift-frontend && npm run lint && npm run build
```

Covers the version detectors and the gated upgrade rules of all four languages, the AST
validator, diff and change counting, the language registry, similarity scoring, all API
routes including the payload limit, the test executor, the scoring models, the language
detector and their dataset, translation semantics (precedence, integer division, loops,
formatted I/O, input, classes and structs, refusals) and a compile check on all 12
pairs. Both suites run in CI on every push.

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
    core/                     gated rule engine, toolchain runner, comment/string masking
    languages/{python,java,c,cpp}/enterprise_engine/
                              per-language rules and version detector

codeshift-frontend/src/       pages, components, services, utils, styles
```

---

## Known limitations

Each program the engine cannot translate faithfully is **refused** with a reason
(`Cannot translate this program faithfully: ...`) rather than translated approximately.
The main gaps, from failures on programs that were never used during development:

- **C as a target** has no growable list or string type: list growth, string building
  and string methods from Python or Java, and C++ containers, `std::string`, classes and
  `<iomanip>`, are refused.
- **Refused C and C++ constructs:** `sizeof`, chained assignment, writes into `char`
  arrays, function-like macros, stream manipulators such as `fixed`, increments inside
  expressions and fall-through `switch` cases. Array members inside structs are not parsed.
- **Refused Java and Python constructs:** lambdas, enums, labels, slicing and keyword
  arguments.
- **Unmapped library calls** (for example C++ `to_string` and `c_str`, Python
  `round(x, n)` and character methods such as `ch.isupper()`) still produce code that does
  not compile or fails at run time.
- **Integer width:** Python's unbounded integers become 32-bit `int`; larger values
  overflow silently.
- Where a Python type cannot be inferred, Java falls back to `Object`; each such decision
  is reported in the semantic findings.
- Single-file programs that use standard input and output only: no multi-file projects,
  concurrency or framework APIs.

**Handled by lowering rather than mapping** — counting loops become `range` only when
provably equivalent (otherwise a `while` loop), `switch` becomes an if/else chain,
`printf`/`%`/f-string formatting goes through one format-string node, list
comprehensions become loops with appends, tuple assignment goes through temporaries, and
Python default arguments become Java overloads.

---

## License

[MIT](LICENSE)
