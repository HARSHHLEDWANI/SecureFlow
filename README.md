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

Environment Variables

Create a .env file at the project root (not inside backend):

DATABASE_URL=postgresql://postgres:password@localhost:5432/secureflow

Run Database Migrations
npx prisma migrate dev --schema backend/prisma/schema.prisma

Start the Backend Server
npm run dev


The backend will start on:

http://localhost:4000

🔌 Backend API Endpoints
Create Transaction
POST /transactions


Request body:

{
  "fromWallet": "0xabc",
  "toWallet": "0xdef",
  "amount": 250,
  "currency": "USD"
}


Response:

201 Created

Transaction stored with status PENDING

Get Transactions
GET /transactions


Response:

List of all transactions

Sorted by most recent first

🤖 AI Service Integration (Internal)

The backend communicates with a separate AI service for fraud risk evaluation.

The AI service exposes /predict-risk

The backend calls this endpoint internally

The AI does not approve or reject transactions

The backend makes all final decisions

The AI service is not exposed directly to clients.

📈 Execution Flow

Client sends transaction request to backend

Backend validates input and stores transaction

Backend requests fraud risk from AI service

Backend decides transaction outcome

(Planned) Blockchain records immutable proof

🧪 Testing the Backend

Invalid input returns 400 Bad Request

Valid transactions are persisted in the database

All errors are handled centrally

The backend acts as the single source of truth for the system.