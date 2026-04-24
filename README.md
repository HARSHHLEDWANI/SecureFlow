# SecureFlow

A payment fraud detection system. Transactions are scored by an ML model, logged immutably on-chain, and managed through a real-time dashboard.

---

## Architecture

```
┌──────────────┐     POST /api/transactions      ┌─────────────────┐
│   Next.js    │ ──────────────────────────────► │  Node/Express   │
│  Frontend    │ ◄────────────────────────────── │    Backend      │
│  (port 3000) │                                 │   (port 4000)   │
└──────────────┘                                 └────────┬────────┘
                                                          │
                                      ┌───────────────────┼───────────────────┐
                                      │                   │                   │
                                      ▼                   ▼                   ▼
                               ┌────────────┐    ┌──────────────┐    ┌──────────────┐
                               │ PostgreSQL  │    │  AI Service  │    │   Sepolia    │
                               │  (Prisma)  │    │  (FastAPI)   │    │  Blockchain  │
                               │  port 5432 │    │  port 8000   │    │  (ethers.js) │
                               └────────────┘    └──────────────┘    └──────────────┘
```

**Trust model:** Backend is the single decision authority. AI service is advisory only. Blockchain provides tamper-proof audit records. No component is trusted alone.

---

## Tech Stack

| Layer       | Technology                                          |
|-------------|-----------------------------------------------------|
| Frontend    | Next.js 16, React 19, Tailwind CSS, Recharts        |
| Backend     | Node.js, TypeScript, Express, Prisma ORM            |
| Database    | PostgreSQL 16                                       |
| AI Service  | Python 3.11, FastAPI, scikit-learn (RandomForest)   |
| Blockchain  | Solidity 0.8.28, Hardhat, ethers.js, Sepolia testnet|

---

## Running Locally

### Prerequisites

- Node.js >= 18
- Python >= 3.11
- PostgreSQL 16 running locally
- A `.env` file in `/backend` (copy from `.env.example`)

### 1. Backend

```bash
cd backend
npm install
npx prisma migrate dev
npx prisma db seed
npm run dev           # starts on port 4000
```

### 2. AI Service

```bash
cd ai-service
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app/train.py        # generates models/fraud_model.joblib
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_URL
npm run dev           # starts on port 3000
```

---

## Environment Variables

| Variable              | Service  | Description                           |
|-----------------------|----------|---------------------------------------|
| `DATABASE_URL`        | backend  | PostgreSQL connection string          |
| `JWT_SECRET`          | backend  | Secret for signing access tokens      |
| `JWT_REFRESH_SECRET`  | backend  | Secret for signing refresh tokens     |
| `AI_SERVICE_URL`      | backend  | URL of the Python AI service          |
| `CONTRACT_ADDRESS`    | backend  | Deployed AuditLog contract address    |
| `SEPOLIA_RPC_URL`     | backend  | Alchemy/Infura Sepolia RPC URL        |
| `FRONTEND_URL`        | backend  | Allowed CORS origin (Vercel URL)      |
| `PORT`                | backend  | HTTP port (default: 4000)             |
| `NEXT_PUBLIC_API_URL` | frontend | Backend API base URL                  |

---

## What's Implemented

- [x] PostgreSQL schema with User, Transaction, AuditLog, ApiKey models
- [x] JWT auth (access + refresh tokens)
- [x] Full CRUD API for transactions and audit logs
- [x] RandomForest ML model for fraud scoring
- [x] Feature engineering pipeline (amount, wallet entropy, velocity, etc.)
- [x] AuditLog Solidity contract deployed on Sepolia testnet
- [x] Blockchain audit logging wired into transaction creation
- [x] Next.js dashboard with real data (no mock data)
- [x] Role-based access (ADMIN, ANALYST, VIEWER)
- [x] API key authentication for external integrations
- [x] Docker Compose for local development
- [x] GitHub Actions CI

## What's Planned

- [ ] WebSocket real-time alerts
- [ ] Multi-wallet portfolio view
- [ ] SAML/SSO integration

---

## Live Demo

- Frontend: https://secure-flow-inky.vercel.app
- Backend: deployed on Railway
- Contract: verified on Sepolia Etherscan
