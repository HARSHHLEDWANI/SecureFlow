COMPONENTS

User + Wallet
     ↓
Frontend (Next.js)
     ↓
Backend (Node + TS)  ← THE BRAIN
  ↙        ↘
AI Service  Blockchain
(FastAPI)  (Solidity)
     ↓
PostgreSQL Database


Core Principle
Frontend = input/output
AI = advisor
Backend = judge
Blockchain = court record
Database = working memory

Responsibilities
Component Responsbilities
Frontend (Next.js)
-Handle user interaction and UI
-Connect wallet and sign messages
-Send transaction requests to backend
-Display transaction status, risk scores, and history
-Not responsible for: decisions, fraud logic, blockchain writes

Backend API (Node.js)
-Authenticate users via wallet signatures
-Validate inputs and enforce business rules
-Orchestrate transaction lifecycle
-Request fraud risk from AI service
-Decide approve / reject / flag
-Persist data to database
-Interact with smart contracts and listen to events
-Single decision authority

AI Fraud Service (FastAPI)
-Analyze transaction features
-Generate fraud risk scores
-Provide confidence and explanations
-Advisory only — never approves or rejects transactions

Smart Contracts (Solidity)
-Store minimal, immutable transaction proofs
-Emit events for off-chain listeners
-Enforce access control
-No business logic or fraud computation

Database (PostgreSQL)
-Store users, wallets, transactions, and fraud scores
-Support queries, analytics, and audits
-Mutable storage — not a source of truth
-Blockchain Event Listener
-Monitor contract events
-Sync on-chain state with database
-Handle confirmations and retries

Architectural Rules
-Backend is the only authority
-AI advises, blockchain proves
-Frontend is untrusted
-Business logic stays off-chain