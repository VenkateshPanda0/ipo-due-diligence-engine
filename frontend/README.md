# IPO Due Diligence Engine Frontend

Frontend source for the IPO Due Diligence Engine. The UI is intentionally thin:
it only calls the FastAPI backend and renders returned reports. Eligibility
logic remains exclusively in the backend rules and decision engines.

Run locally:

```bash
npm install
npm run build
```
