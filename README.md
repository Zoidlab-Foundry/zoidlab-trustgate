# ZoidLab TrustGate — AI Policy Engine

**Foundry Package 06 · Live at [trustgate.zoidlab.ai](https://trustgate.zoidlab.ai) · Nyquest Pro required**

TrustGate is the control point between user intent and AI execution. It answers one
question: **"Is this AI action allowed?"** — define, test, enforce, and audit AI usage
policies across models, prompts, agents, workflows, RAG, memory, tools, and data types.

## Spine
Policy project → policies + rules → **test an action** → allow / warn / require-approval / block
→ violations log → approval queue → export the **Nyquest Policy Package**.

The policy engine is **real and deterministic** (regex secret/PII detection, model allow/deny
lists, approval triggers, citation requirements, cost limits, tool restrictions) — no
fabricated scoring.

## Stack
- Frontend: Next.js 15, React 19, TypeScript, TailwindCSS (dark), reusable Foundry Pro gate.
- Backend: FastAPI, SQLite (Postgres-portable), every write + check behind `require_pro`.
- Auth: shared ZoidLab / Nyquest SSO cookie + Foundry entitlement (frontend + backend enforced).

## Local
```bash
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
MOCK_PRO_USER=true uvicorn main:app --port 8700
cd ../frontend && npm install && npm run dev
```

## API (all require Nyquest Pro)
Projects, Policies (CRUD + versions + test), `POST /api/test` (core check), Violations,
Approvals (approve/reject), Analytics, `GET /api/export/json|yaml`.

## Package export
`trustgate.package.json` — `package_type: nyquest_policy_package` (policies, rules,
enforcement modes, applies-to, governance, test cases).

## Deploy (trustgate.zoidlab.ai)
systemd `trustgate-api` (:8700) + `trustgate-web` (:3700) behind the shared Cloudflare Tunnel.
Listed on foundry.zoidlab.ai as Package 06.
