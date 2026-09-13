# CodeShift — frontend

React 19 + Vite + Monaco UI for the CodeShift migration engines.
See the [root README](../README.md) for the full project overview, API reference and screenshots.

```bash
npm install
npm run dev      # http://localhost:5173, proxies /api -> http://127.0.0.1:5000
```

The backend must be running (`cd ../codeshift-backend && python flask_app.py`).
Copy `.env.example` to `.env` only if you need to point at a different API host.

| Script | Purpose |
| --- | --- |
| `npm run dev` | dev server with HMR |
| `npm run build` | production bundle into `dist/` |
| `npm run preview` | serve the built bundle |
| `npm run lint` | ESLint |

## Layout

```
src/
  pages/         Landing, Migration
  routes/        AppRoutes.jsx
  components/    landing/, layout/, migration/{steps,workspace,report}
  context/       MigrationContext.jsx
  services/      migrationService.js — the only module that calls the API
  utils/         language.js — label -> Monaco id / file extension
  styles/        global, layout, landing, migration
```
