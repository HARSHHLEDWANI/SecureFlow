# SecureFlow — API Reference

Complete reference for every HTTP route and the one WebSocket route in the
SecureFlow backend (`backend/app/api/`). Grouped by router.

- **Base URL**: all REST routes are mounted under `/api/v1` (e.g. `/api/v1/health`).
  The WebSocket is mounted at `/ws/alerts` (no version prefix).
- **Response envelope**: every REST route returns
  `{ "success": bool, "data": <payload>, "error": string|null }` (see
  `app/dependencies.py::envelope`). Errors raised via `HTTPException` return
  FastAPI's `{ "detail": "..." }` with the appropriate status code.
- **Auth**: send `Authorization: Bearer <access_token>`. The token is issued by
  `/auth/login` (or `/auth/verify-step-up`) and resolved by
  `get_current_user` (`app/dependencies.py`). A refresh token is stored in an
  httpOnly `sf_refresh` cookie.
- **Auth levels used below**:
  - **none** — no authentication required
  - **auth** — any authenticated user (`get_current_user`)
  - **owner/staff** — any authenticated user, but VIEWERs are restricted to their
    own data; ANALYST/ADMIN see everything (`is_staff`)
  - **staff** — ANALYST or ADMIN only (`require_staff`)
  - **governance** — governance council member or the main admin (`gov_access`)

---

## Health — `app/api/routes/health.py`

### `GET /api/v1/health`
- **Purpose**: Liveness/readiness probe reporting subsystem status.
- **Auth**: none.
- **Request body**: none.
- **Response** `data`: `{ status: "ok", version, redis: bool, database: bool, model_loaded: bool, model_version: str|null, blockchain_blocks: int }`.
- **Calls into**: `redis_client.ping()`, a `SELECT 1` against `engine`,
  `get_model_service()`, `get_blockchain()`.
- **Notes**: Never fails on subsystem outage — reports each subsystem's boolean
  status instead. Used as Render's `healthCheckPath`.

---

## Auth — `app/api/routes/auth.py`

All auth routes are rate-limited per-IP (`RateLimiter`, fail-open via Redis).

### `POST /api/v1/auth/register`
- **Purpose**: Create a new user account.
- **Auth**: none.
- **Body**: `RegisterRequest` (`app/models/user.py`) — `email` (EmailStr),
  `password` (8–128 chars), `vpa` (regex `^[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z]{2,64}$`),
  `home_city` (default "Mumbai").
- **Response** `data`: `UserPublic` (`id, email, vpa, role, home_city, governance_access`).
- **Behavior**: The **first real registrant becomes ADMIN**; everyone else is a
  VIEWER (seeded `@secureflow.local`/`@secureflow.io` accounts are excluded from
  that check). 409 on duplicate email. `201 Created`.

### `POST /api/v1/auth/login`
- **Purpose**: Authenticate; login is itself risk-scored.
- **Auth**: none.
- **Body**: `LoginRequest` — `email`, `password`, `device_id` (default "web-default").
- **Response** `data`: `LoginResponse` — on LOW risk returns `access_token` + `user`;
  on MEDIUM risk returns `step_up_required=true`, `challenge_id`, and `demo_otp`
  (demo only — normally delivered out-of-band); HIGH risk raises 403.
- **Calls into**: `verify_password` (bcrypt), `_assess_login_risk`
  (unknown-device / odd-hour / weak-fingerprint scoring), `redis_client.set_session`
  for the step-up challenge, `create_token` + `set_cookie` for the refresh token.

### `POST /api/v1/auth/verify-step-up`
- **Purpose**: Complete a MEDIUM-risk login by verifying the OTP challenge.
- **Auth**: none (bearer of a valid `challenge_id`).
- **Body**: `StepUpRequest` — `challenge_id`, `otp` (4–8 chars).
- **Response** `data`: `LoginResponse` with an `access_token`.
- **Behavior**: `secrets.compare_digest` OTP check; 400 if the challenge expired,
  401 on wrong OTP. Consumes the Redis session and marks the device known.

### `POST /api/v1/auth/refresh`
- **Purpose**: Rotate the access token using the httpOnly refresh cookie.
- **Auth**: valid `sf_refresh` cookie.
- **Body**: none.
- **Response** `data`: `{ accessToken }`. 401 if the cookie is missing/invalid.

### `GET /api/v1/auth/me`
- **Purpose**: Return the current user (including their governance-access flag).
- **Auth**: auth.
- **Response** `data`: `UserPublic` with `governance_access` set from
  `has_governance_access`.

### `POST /api/v1/auth/logout`
- **Purpose**: Clear the refresh cookie.
- **Auth**: none (idempotent). **Response** `data`: `{ loggedOut: true }`.

---

## Transactions — `app/api/routes/transaction.py`

### `POST /api/v1/transaction/analyze`
- **Purpose**: Run the full fraud-analysis pipeline and record the result on-chain.
- **Auth**: auth (analyses run as the calling user).
- **Rate-limited**: yes (`RateLimiter("analyze")`).
- **Body**: `TransactionAnalyzeRequest` — `to_vpa` (VPA regex), `amount_inr`
  (`>0, ≤10,000,000`), `txn_type` (`P2P|P2M|BILL_PAY`), `device_id`,
  `location_lat` (−90..90), `location_lon` (−180..180).
- **Response** `data`: `TransactionResult` — full assessment incl. `risk_score`,
  `risk_tier`, `status`, `ml_fraud_prob`, `anomaly_score`, `components`,
  `feature_contributions`, `block_index`, `block_hash`, `recommended_action`.
- **Calls into**: `gather_signals` then `run_pipeline` (`app/core/pipeline.py`),
  which uses Redis for velocity/geo/device lookups (DB fallback), the trained
  model via `app/ml/model.py`, composite scoring via `app/core/risk_engine.py`,
  mines a block via `app/core/blockchain.py`, writes an `AuditLog`, refreshes
  Redis caches, and dispatches a WebSocket alert when the tier is HIGH.

### `GET /api/v1/transaction/{txn_id}/status`
- **Purpose**: Fetch a stored transaction summary.
- **Auth**: owner/staff — a VIEWER may only read their **own** transaction;
  cross-user reads return **404** (so the id's existence isn't leaked).
- **Response** `data`: `TransactionSummary`.

### `GET /api/v1/transaction`
- **Purpose**: List recent transactions, newest first.
- **Auth**: owner/staff — ANALYST/ADMIN see **all** transactions; a VIEWER sees
  only their own (`Transaction.user_id == current_user.id`).
- **Query**: `limit` (1–200, default 50), `tier` (`LOW|MEDIUM|HIGH`, optional).
- **Response** `data`: `TransactionSummary[]`.

### `POST /api/v1/transaction/{txn_id}/explain`
- **Purpose**: Return a plain-English, 2–3 sentence explanation of an
  already-made fraud decision (Feature A).
- **Auth**: owner/staff — **same** ownership rule as `/{txn_id}/status` (reuses the
  `_txn_or_404` helper): a VIEWER may only explain their own transaction, staff any;
  cross-user → 404.
- **Rate-limited**: yes, and **more tightly** than other endpoints
  (`RateLimiter("explain", limit=explain_rate_limit_requests)`, default 10/window)
  because it has a real per-call cost.
- **Request body**: none.
- **Response** `data`: `ExplanationResult` (`app/models/transaction.py`) —
  `explanation` (str), `source` (`"llm"` | `"template"`), `cached` (bool).
- **Calls into**: reconstructs the decision context from the stored `ANALYZE_*`
  `AuditLog` metadata (`components` + `feature_contributions`), then
  `app/core/explain.py::explain_decision`. That calls the Groq API
  (`explain_model`, a small/fast/cheap model) with a hard timeout; **the LLM only
  explains — it never influences the score/tier/action**. On no key / error /
  timeout it falls back to a deterministic template (`source: "template"`).
- **Caching**: Redis `explain:{txn_id}` (TTL 24h) so repeat clicks don't re-spend
  budget; degrades gracefully if Redis is down. **This is the only endpoint with
  an external cost dependency** — see docs/TECH_STACK_AND_ALTERNATIVES.md.

### `GET /api/v1/risk-score/{user_id}`
- **Purpose**: Return a user's aggregate risk profile.
- **Auth**: owner/staff — a VIEWER may only read their own profile (**403**
  otherwise); ANALYST/ADMIN may read any user's.
- **Response** `data`: `UserRiskProfile` — `transaction_count`,
  `average_risk_score`, `flagged_count`, `last_risk_score`, `cached`.
- **Notes**: Served from Redis (`risk:user:{id}`, TTL 300s) when warm; recomputed
  from the DB via `compute_risk_profile` on a miss.

---

## Blockchain explorer — `app/api/routes/blockchain.py`

All four routes are **staff**-gated (ANALYST/ADMIN) — they expose every user's
audit data.

### `GET /api/v1/blockchain/chain`
- Full audit chain. **Response** `data`: `{ length, chain: Block[] }`.

### `GET /api/v1/blockchain/validate`
- Validate integrity + report the first tampered block.
- **Response** `data`: `{ valid: bool, tampered_block: int|null, message }`.
- **Calls into**: `Blockchain.tamper_detection()` + `validate_chain()`.

### `GET /api/v1/blockchain/stats`
- **Response** `data`: `{ blocks, total_transactions, difficulty, valid, genesis_timestamp, latest_hash }`.

### `GET /api/v1/blockchain/block/{index}`
- A single block by index. **404** if out of range.

---

## Analytics — `app/api/routes/analytics.py`

All three routes are **staff**-gated (aggregate views over all users).

### `GET /api/v1/analytics/dashboard`
- **Purpose**: Aggregated fraud KPIs for the dashboard.
- **Response** `data`: `{ total_transactions, fraud_detected, fraud_rate,
  average_risk_score, blocked_count, step_up_count, tier_distribution,
  daily_volume[7], risk_score_histogram[10] }`.
- **Notes**: Redis-cached for 60s (`analytics:dashboard`); volume/histogram are
  computed in Python for DB portability.

### `GET /api/v1/analytics/recent-alerts`
- Most recent non-LOW transactions, newest first. **Query**: `limit` (1–100, def 20).

### `GET /api/v1/analytics/model-metrics`
- The stored evaluation metrics from the last training run
  (`data/model_metrics.json`). Returns `error` in the envelope if the file is
  absent/unreadable (still `200`).

---

## UPI Simulation Lab — `app/api/routes/upi.py`

**Intentionally unauthenticated** — a one-click public demo surface that acts on
the *seeded demo users*, never on real accounts. `/pay`, `/scenario`, and
`/rapid-fire` are rate-limited.

### `GET /api/v1/upi/users`
- Demo user profiles with a live transaction count + last risk score.
- **Response** `data`: `{ users: [...], demo_password, cities }`.

### `GET /api/v1/upi/scenarios`
- All preset attack/behaviour scenarios. **Response** `data`: `{ scenarios: [...] }`.

### `POST /api/v1/upi/pay`
- **Purpose**: Process one UPI payment through the **real** pipeline.
- **Body**: `UPIPayRequest` — `sender_vpa`, `receiver_vpa` (both VPA regex),
  `amount_inr`, `txn_type`, `note?`, `city?`, `device_id?`.
- **Response** `data`: `UPIPayResult` — decision (`APPROVED|STEP_UP|BLOCKED`),
  risk score/tier, ML outputs, `feature_contributions`, `block_index/hash`,
  `total_duration_ms`, and the per-stage `pipeline` snapshot.
- **Calls into**: `simulator.process_payment` → `gather_signals` + `run_pipeline`
  (same pipeline as `/transaction/analyze`, plus a `StageTracker` for live timing).
  422 on invalid VPA / unknown sender.

### `POST /api/v1/upi/scenario/{scenario_id}`
- Run one preset scenario end-to-end (deterministic signal overrides). **404** if
  unknown. Resets the sender's rolling baseline first so scenarios are repeatable
  regardless of order.

### `POST /api/v1/upi/rapid-fire`
- Run the 10-payment rapid-fire burst; returns the full sequence (velocity
  escalation demo).

### `GET /api/v1/upi/user/{vpa}/history`
- Recent transactions for a demo user. **Query**: `limit` (1–100, def 25).

### `GET /api/v1/upi/pipeline-status/{txn_id}`
- Live per-stage pipeline timing for a transaction (from Redis). **404** if none.

### `POST /api/v1/upi/reset`
- Reset all demo data (users + history) to the seeded state. **Response** `data`:
  `{ reset: true, users_seeded }`.

---

## Governance — `app/api/routes/governance.py`

All routes are **governance**-gated via `gov_access` (council members + main
admin). See `app/core/governance.py`.

### `GET /api/v1/governance/council`
- Council roster + demo login password. **Response** `data`:
  `{ members, size, threshold: "unanimous", demo_password }`.

### `GET /api/v1/governance/proposals`
- List override proposals, newest first. **Query**: `status`
  (`PENDING|APPLIED|REJECTED|DIVERGED`), `limit` (1–200, def 50).

### `POST /api/v1/governance/proposals`
- **Purpose**: Propose reversing a transaction's fraud decision.
- **Body**: `ProposalCreate` — `transaction_id`, `proposed_status`
  (`ALLOWED|STEP_UP|BLOCKED`), `reason` (3–500 chars).
- **Behavior**: Only a **council** member may propose; the proposer implicitly
  casts the first APPROVE. 400 on identical status / open proposal exists /
  non-council proposer. `201 Created`.

### `GET /api/v1/governance/proposals/{proposal_id}`
- One proposal with its full vote list. **404** if not found.

### `POST /api/v1/governance/proposals/{proposal_id}/vote`
- **Purpose**: Cast a vote. **Body**: `VoteRequest` — `vote` (`APPROVE|REJECT`).
- **Behavior**: Records the admin's independent state attestation; any single
  REJECT rejects; a mid-vote state change flags **DIVERGED** and discards; on the
  final unanimous APPROVE the change is applied and **sealed on-chain**.

### `GET /api/v1/governance/integrity/{txn_id}`
- Compare the live DB record against the immutable on-chain agreed state.
  **Response** `data`: `{ verified, tampered, current, agreed }`.

### `POST /api/v1/governance/integrity/{txn_id}/rollback`
- Restore a tampered transaction to its on-chain agreed state (seals a
  `GOVERNANCE_ROLLBACK` block).

### `POST /api/v1/governance/integrity/{txn_id}/simulate-tamper`
- **DEMO-ONLY**: a rogue direct DB edit that bypasses consensus + chain, to show
  detection. **Body**: `TamperRequest` — `new_status`.

### `GET /api/v1/governance/watchdog`
- State of the automatic self-healing watchdog (`enabled`, `interval_seconds`,
  `runs`, `checked`, `healed_total`, `recent`).

### `POST /api/v1/governance/watchdog/scan`
- Run one integrity scan immediately (auto-heals any tampering found).

### `GET /api/v1/governance/feedback/summary`
- **Purpose**: State of the governance→model feedback loop (Feature B).
- **Response** `data`: `{ unconsumed_corrections, min_examples, live_metrics,
  candidates: [{ version, metrics, n_corrections, regression }], retrain_status }`.
- **Calls into**: `app/ml/feedback.py` (`unconsumed_count`, `live_metrics`,
  `list_candidates`).

### `POST /api/v1/governance/feedback/retrain`
- **Purpose**: Retrain a **versioned candidate** model on the synthetic dataset +
  the approved, unconsumed corrections (weighted higher). Runs as a FastAPI
  `BackgroundTasks` job (a full grid-search retrain is ~25–30s) — poll
  `feedback/summary`'s `retrain_status`. **Never promotes.**
- **Behavior**: 400 if there are fewer than `feedback_min_examples` corrections;
  409 if a retrain is already running. Uses only transactions that have a
  persisted `feature_snapshot` (scored after Feature B shipped) — see the note in
  the Transactions/Feedback design.
- **Calls into**: `feedback.run_retrain_job` → `run_feedback_retrain`.

### `POST /api/v1/governance/feedback/promote`
- **Purpose**: Make a candidate version the live model.
- **Body**: `PromoteRequest` — `version` (int ≥1), `force` (bool).
- **Behavior**: The **regression guard** blocks promotion if the candidate's
  AUC/recall drop beyond the configured thresholds vs the live model, unless
  `force=true`. On success, swaps in the model, reloads the model singleton
  (`reload_model_service`), and marks the folded-in corrections
  `consumed_for_training=True` (only on success). 400 on a blocked/unknown candidate.

---

## WebSocket — `app/api/websockets/alerts.py`

### `WS /ws/alerts?token=<access_token>`
- **Purpose**: Stream live fraud alerts (`fraud_alert`) and integrity auto-heal
  events (`integrity_autoheal`) to the dashboard in real time.
- **Auth**: **required** — a valid access token must be supplied via the `?token=`
  query parameter (browsers can't set an `Authorization` header on a WS
  handshake). A missing/invalid token is rejected with close code **1008**
  *before* the connection is accepted; there is no anonymous feed.
- **Protocol**: on connect the server sends `{ type: "connected", channel:
  "fraud:alerts" }`, then pushes alert JSON as it arrives. Clients need not send
  anything.
- **Bus**: `dispatch_alert` publishes to the Redis `fraud:alerts` channel; a
  background `redis_alert_listener` fans messages out to all clients. If Redis is
  unavailable it falls back to an in-process broadcast so a single-node deployment
  still gets live alerts.
