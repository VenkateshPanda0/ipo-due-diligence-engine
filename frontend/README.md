# Frontend — IPO Due Diligence Engine

Next.js 15 (pages router) + React 19 + TanStack Query + zod. The UI never computes
regulatory outcomes: it renders what the backend returns and validates critical
responses at runtime.

```bash
npm ci
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev   # http://localhost:3000
npm run typecheck
npm test                 # Vitest component/unit tests
npm run build
# End-to-end (needs backend on :8000 and `npm start` on :3000):
npx playwright test      # set E2E_SCREENSHOT_DIR=... to save screenshots
```

Sections: dashboard, screening cases (guided workflow), documents, evidence &
data (provenance per value, manual entry), review workspace, screening reports
(rule assessment, evidence register with page previews, gap planner,
limitations, human sign-off), rule explorer, settings & system health.
