# SecureFlow

SecureFlow is a backend-orchestrated payment security system where AI evaluates risk, the backend decides outcomes, and blockchain provides immutable auditability.

---

## 🧠 Overview

SecureFlow is built with a strict separation of responsibilities:

- **AI Service** evaluates fraud risk and returns advisory signals
- **Backend** is the single decision authority
- **Blockchain** (planned) provides immutable audit logs
- **Database** stores operational and audit data

No single component is trusted alone.  
The backend orchestrates and enforces all decisions.

---

## 🏗 Monorepo Structure



---

## ⚙️ Tech Stack

### Backend
- Node.js
- TypeScript
- Express
- Prisma ORM
- PostgreSQL
- Zod (validation)

### AI Service
- Python
- FastAPI
- Pydantic
- scikit-learn (planned)

### Planned
- Solidity + Hardhat (Blockchain)
- Next.js (Frontend)

---

## 🔌 Services

### Backend API
- Handles transaction creation and retrieval
- Validates input and enforces business rules
- Orchestrates AI and blockchain integrations

### AI Fraud Detection Service
- Exposes an internal `/predict-risk` endpoint
- Accepts transaction data
- Returns:
  - `risk_score` (0–1)
  - `confidence`
  - `explanation`
- **Advisory only** — never approves or rejects transactions

The AI service is **not exposed directly to clients**.

---

## 🚀 Running Locally

### Prerequisites
- Node.js (>=18)
- Python (>=3.10)
- PostgreSQL

---

### Backend Setup

```bash
cd backend
npm install
npm run dev

