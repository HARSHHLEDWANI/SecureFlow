# SecureFlow — Functions Catalog

A file-by-file catalog of the functions, methods, classes, and exported
components across `backend/app/` and `frontend/src/`. Organised to mirror the
project structure. `legacy/` is intentionally excluded (archived, disconnected
from the active app).

---

# Backend — `backend/app/`

## `config.py`
- **`Settings`** (pydantic-settings) — strongly-typed app configuration from env
  vars: app/db/redis/JWT/ML/blockchain/rate-limit/watchdog settings. Notable:
  `blockchain_storage` (`file`|`db`), `cors_origins_list` and `is_production`
  properties.
- **`get_settings()`** — returns the process-wide cached `Settings` (`lru_cache`).
  Called almost everywhere; `cache_clear()` is used by tests to re-read env.

## `database.py`
- **`engine` / `SessionLocal`** — SQLAlchemy 2.0 engine + session factory,
  configured from `DATABASE_URL` (SQLite gets `check_same_thread=False`).
- **Enums**: `Role` (ADMIN/ANALYST/VIEWER), `TxnType`, `RiskTier`, `TxnStatus`,
  `ProposalStatus`, `VoteType`.
- **`User`** — account (email, bcrypt `password_hash`, `vpa`, `role`, `home_city`).
- **`Transaction`** — a scored payment (parties, amount, geo/device, risk score/tier,
  ML outputs, status, `block_index`/`block_hash`).
- **`AuditLog`** — immutable action record linked to a transaction + actor.
- **`OverrideProposal`** — a proposed fraud-decision reversal with a `state_hash`
  snapshot for divergence detection.
- **`ProposalVote`** — one admin's vote + independent state attestation (unique per
  proposal+admin).
- **`ChainBlock`** — persisted blockchain block (the durable DB storage backend for
  the audit chain).
- **`init_db()`** — create all tables (idempotent), called on startup.
- **`get_db()`** — FastAPI dependency yielding a session, closed afterwards.

## `dependencies.py`
- **`envelope(data, error, meta)`** — builds the standard `{success,data,error}`
  response envelope used by every route.
- **`get_current_user(...)`** — resolves the authenticated `User` from the Bearer
  token (raises 401 on missing/expired/invalid/unknown).
- **`require_role(*roles)`** — dependency factory enforcing a role allow-list.
- **`is_staff(user)`** — True for ANALYST/ADMIN (full fraud-ops visibility); used for
  ownership checks in the transaction routes.
- **`require_staff(user)`** — dependency gating a route to ANALYST/ADMIN; used by the
  analytics + blockchain routers.
- **`RateLimiter`** — per-IP/endpoint fixed-window limiter (fail-open via
  `redis_client.rate_limit_hit`).

## `main.py`
- **`lifespan(app)`** — startup/shutdown: `init_db`, ensure genesis block, load the
  model, seed demo users + governance council, start the Redis→WS alert listener and
  the integrity watchdog; cancels both on shutdown.
- **`_unhandled(request, exc)`** — global exception handler returning a JSON envelope.
- **`app`** — the FastAPI instance; includes all routers under `/api/v1` and the WS
  router; `root()` returns basic service info.

## `core/blockchain.py`
- **`Block`** (dataclass) — a block; `compute_hash()` (SHA-256 over content),
  `to_dict()`/`from_dict()`.
- **`Blockchain`** — append-only PoW chain. `_load_or_init` / `_load_from_file` /
  `_load_from_db` (storage backends), `_persist` / `_persist_to_file` /
  `_persist_to_db`, `_mine` (nonce brute-force), `mine_block`, `add_transaction`,
  `get_chain`, `get_block`, `validate_chain`, `tamper_detection` (first broken
  block), `stats`.
- **`get_blockchain()`** — process-wide singleton (lazy, thread-safe), built with the
  configured storage backend.

## `core/pipeline.py`
The single source of truth for the transaction-analysis flow.
- **`StageTracker`** — records per-stage timing for the Lab visualizer; `mark`,
  `rekey`, `snapshot`, mirrored into Redis. Used only by the Lab (zero prod overhead).
- **`aware(dt)`** — normalises a naive DB datetime to aware UTC.
- **`_user_amount_stats(db, user_id)`** — (avg, std) of a user's historical amounts.
- **`_db_velocity(db, user_id, window, now)`** — DB fallback for velocity counts.
- **`gather_signals(...)`** — assembles raw fraud signals (velocity, geo-velocity,
  new-device, new-beneficiary, amount stats) from Redis with a DB fallback; supports
  deterministic `overrides` for the Lab.
- **`predict_cached(signals)`** — ML prediction with the same Redis cache the analyze
  route uses (`prediction:{hash}`).
- **`run_pipeline(...)`** — the pipeline: predict → composite risk → persist txn →
  mine a block → write audit log → update Redis history → dispatch a HIGH alert.
  Returns `(txn, ml_result, risk)`.
- **`recommended_action(status)`** — human-readable action string.
- **`refresh_risk_cache(db, user_id, last_score)`** / **`compute_risk_profile(...)`**
  — recompute + cache a user's aggregate risk profile.

## `core/risk_engine.py`
- **`WEIGHTS`** — signal weights (sum 100): ml_fraud 40, anomaly 15, velocity 15,
  geo 12, new_device 8, amount 6, time 4.
- **`_tier_and_status(score)`** — LOW≤30→ALLOWED, ≤70→STEP_UP, else BLOCKED.
- **`compute_risk(features, ml_result)`** — blends ML + rule signals into the 0–100
  composite score, tier, status, and per-component contributions.

## `core/redis_client.py`
- **`RedisClient`** — fail-open wrapper over a pooled Redis connection. `_safe`
  (swallows errors, returns a neutral default), `ping`, JSON cache
  (`cache_get_json`/`cache_set_json`), `rate_limit_hit`, velocity
  (`record_velocity`/`velocity_count` via sorted sets), geo
  (`set_last_geo`/`get_last_geo`), device sets (`is_known_device`/`add_device`),
  sessions (`set_session`/`get_session`/`delete_session`), queue, and
  `publish_alert` (pub/sub).
- **`redis_client`** — module-level singleton.

## `core/security.py`
- **`hash_password` / `verify_password`** — bcrypt hashing + constant-time check.
- **`create_token(subject, type, **claims)`** — signed JWT with configured expiry.
- **`decode_token(token, type)`** — decode/validate a JWT (raises `PyJWTError`).

## `core/explain.py` (Feature A — "Explain This Decision")
The LLM **explains an already-made decision**; it never influences the score/tier/action.
- **`build_facts(txn, components, feature_contributions)`** — assemble the structured,
  decision-already-made context passed to the model.
- **`template_explanation(...)`** — deterministic fallback built from the strongest
  risk components (used when the LLM is unavailable/errors/times out).
- **`_llm_explanation(facts)`** — call the Anthropic API (small/fast/cheap model, hard
  timeout, `max_retries=0`); raises on any failure so the caller falls back.
- **`explain_decision(txn, components, feature_contributions)`** — returns
  `{explanation, source}`; tries the LLM when a key is configured, else the template.
  Never raises.

## `core/governance.py`
Multi-admin consensus + the self-healing watchdog.
- **`seed_council()` / `council_members` / `council_size` / `is_council`** — the
  fixed 4-admin council.
- **`main_admin(db)` / `is_main_admin` / `has_governance_access`** — the oldest real
  ADMIN + governance access rule (council or main admin).
- **`governed_state(txn)` / `state_hash(txn)`** — the governed fields + their hash.
- **`agreed_state_from_chain(txn_id)`** — the newest on-chain governed state for a txn
  (the immutable source of truth).
- **`create_proposal(...)`** — validate + create a proposal; the proposer auto-approves.
- **`cast_vote(...)`** — record a vote, then `_evaluate`.
- **`_record_vote` / `_evaluate` / `_apply`** — attestation + divergence detection;
  resolve on REJECT / DIVERGED / unanimous APPROVE; `_apply` mines a
  `GOVERNANCE_OVERRIDE` block.
- **`verify_integrity(db, txn_id)`** — compare live DB vs on-chain agreed state.
- **`rollback_from_chain(...)`** — restore a tampered txn from the chain (manual or
  `auto`); mines a rollback/autoheal block.
- **`scan_and_heal_once()`** — verify every anchored txn, auto-heal tampering, emit
  alerts; updates `watchdog_state`.
- **`integrity_watchdog()`** — background loop calling `scan_and_heal_once` on an
  interval.
- **`simulate_tamper(db, txn_id, new_status)`** — DEMO-only rogue DB edit.

## `core/demo_data.py`
- **`CITIES`**, **`DEMO_PASSWORD`**, **`DEMO_USERS`**, **`ATTACK_SCENARIOS`**, and the
  derived lookups `DEMO_USER_BY_VPA`, `SCENARIO_BY_ID` — static Lab data (users with
  history profiles + seven preset attack scenarios).

## `core/demo_seed.py`
- **`demo_user_id(vpa)`** — deterministic UUID5 id for a demo user.
- **`is_demo_user(user)`** — True for `@secureflow.local` accounts.
- **`_seed_history` / `_prime_redis` / `_reset_velocity`** — build ~30 days of
  low-risk history + prime Redis device/geo.
- **`seed_demo_users(force)`** — idempotently ensure demo users + history exist.
- **`reset_sender_baseline(vpa)`** — reset a sender's rolling state before a scenario
  (makes scenarios repeatable).
- **`reset_demo()`** — full Lab reset (used by `/upi/reset`).

## `core/upi_simulator.py`
- **`UPIValidationError`** — invalid Lab input → HTTP 422.
- **`UPISimulator`** — `resolve_sender`, `city_coords`, `process_payment` (builds
  signals + runs the real pipeline with a `StageTracker`), `run_scenario`,
  `run_rapid_fire` (velocity-escalation burst).
- **`_scenario_public` / `_expected_match` / `scenarios_public`** — frontend-safe
  scenario cards + intent matching.
- **`simulator`** — module-level singleton.

## `ml/features.py`
- **`FEATURE_COLUMNS`** — the canonical ordered feature list.
- **`extract_features(raw)`** — turn raw signals into the numeric feature dict
  (amount/log/z-score, tx-type one-hots, hour/night/weekend, velocity, geo +
  impossible-travel, new-device/new-beneficiary). **Shared by training and
  inference** so they never drift.
- **`to_vector(features)`** — order a feature dict into the model input vector.

## `ml/model.py`
- **`ModelService`** — loads the joblib bundle once; `predict` (fraud prob + anomaly
  + confidence + top feature contributions), `_anomaly_score`, `_contributions`,
  `_heuristic` (interpretable fallback when no trained model exists).
- **`get_model_service()`** — process-wide singleton (lazy, thread-safe).

## `ml/training.py`
- **`_make_user_profiles` / `_legit_signals` / `_fraud_signals`** — synthetic UPI
  data generation from independent latent fraud archetypes (takeover/scam/travel/micro).
- **`generate_dataset(...)`** — labelled feature DataFrame with injected label noise.
- **`run_training(fast=False)`** — train + persist the RandomForest + IsolationForest
  bundle and metrics; `fast=True` skips `GridSearchCV` (fixed hyperparameters) for
  test fixtures. Returns the metrics dict.
- **`main()`** — full grid-search training (`python -m app.ml.training`).

## `ml/evaluation.py`
- **`compute_metrics(y_true, y_pred, y_proba)`** — accuracy/precision/recall/f1/AUC +
  confusion matrix.
- **`feature_importance(clf, columns)`** — ranked feature importances.

## `ml/feedback.py` (Feature B — governance → model feedback loop)
- **`collect_feedback_examples(db)` / `unconsumed_count(db)`** — approved, not-yet-
  consumed council corrections joined to each transaction's persisted
  `feature_snapshot` (never a recomputed vector); labeled fraud/legit.
- **`run_feedback_retrain(db, fast=False)`** — retrain on synthetic data + weighted
  corrections (`sample_weight`); writes a **versioned candidate** (`fraud_model_v{n}`
  + metrics) — never overwrites the live model. Returns candidate metrics + the guard.
- **`evaluate_regression_guard(candidate)`** / **`live_metrics()`** — compare a
  candidate's AUC/recall to the live model; block on a material drop.
- **`promote_candidate(db, version, force=False)`** — the only path that makes a
  candidate live: honors the guard (unless `force`), swaps the model file, calls
  `reload_model_service`, and marks corrections `consumed_for_training` on success.
- **`list_candidates()`** — metadata for all on-disk candidates.
- **`run_retrain_job()` + `retrain_status`** — background entry point + pollable status.

## `ml/model.py` (addition)
- **`reload_model_service()`** — force the model singleton to reload from disk (used
  after a promotion swaps in a new model).

## `models/` (Pydantic schemas)
- **`user.py`** — `RegisterRequest`, `LoginRequest`, `StepUpRequest`, `UserPublic`,
  `LoginResponse`.
- **`transaction.py`** — `TransactionAnalyzeRequest`, `RiskComponents`,
  `FeatureContribution`, `TransactionResult`, `TransactionSummary`, `UserRiskProfile`,
  `ExplanationResult` (Feature A).
- **`upi.py`** — `UPIPayRequest`, `UPIPayResult` (VPA-pattern validated).
- **`governance.py`** — `ProposalCreate`, `VoteRequest`, `TamperRequest`,
  `PromoteRequest` (Feature B).
- **`analytics.py` / `blockchain.py`** — response schemas for the analytics and
  blockchain routes.

## `utils/`
- **`helpers.py`** — `utcnow`, `stable_hash` (deterministic SHA-256 of a payload, used
  for ML cache keys), `haversine_km` (geo distance), `clamp`.
- **`logger.py`** — `get_logger(name)` configured application logger.

## `api/` (routers & websocket)
See **API_REFERENCE.md** for every endpoint. Route modules:
`routes/health.py`, `routes/auth.py`, `routes/transaction.py`,
`routes/blockchain.py`, `routes/analytics.py`, `routes/upi.py`,
`routes/governance.py` (with `gov_access`), and `websockets/alerts.py`
(`ConnectionManager`, `dispatch_alert`, `redis_alert_listener`, `alerts_ws`).

---

# Frontend — `frontend/src/`

## `lib/`
- **`api.ts`** — typed API client. `getToken/setToken/clearToken`, `ApiError`,
  `request` (adds bearer, auto-refreshes on 401), `tryRefresh`, and the grouped
  `api` object (auth, transactions, blockchain, analytics, `api.upi.*`,
  `api.governance.*`).
- **`auth.tsx`** — `getDeviceId()` (stable per-browser fingerprint), `AuthProvider`
  (`refresh`/`setSession`/`logout` context), `useAuth()`.
- **`format.ts`** — `formatINR`, `formatNumber`, `formatDateTime`, `shortHash`,
  `TIER_META`, `tierColor`.
- **`labFormat.ts`** — `DECISION_META`, `STAGE_LABELS`, `UPI_HANDLES`,
  `upiDeepLink()`.
- **`types.ts`** — shared TypeScript types (`RiskTier`, `AuthUser`, `DashboardStats`,
  `Alert`, `Block`, `Proposal`, `UpiPayResult`, `PipelineSnapshot`, …).

## `hooks/`
- **`useWebSocket.ts`** — `useAlertStream()`: a shared, ref-counted WebSocket to
  `/ws/alerts` (one socket across all subscribers via `useSyncExternalStore`), sends
  the access token, auto-reconnects, exposes `{ alerts, state }`.

## `components/`
- **`AppShell.tsx`** — the authenticated app layout: desktop sidebar, **mobile header
  + slide-in drawer** (framer-motion), active-route glow, new-HIGH-alert nav pulse
  (`useHighAlertPulse`), and a `PublicChrome` fallback so the Lab is reachable
  logged-out. Exports the default `AppShell`; internal `NavList`, `Brand`,
  `isActive`, `isPublicRoute`.
- **`ui.tsx`** — `Panel`, `StatCard`, `TierBadge`, `Skeleton`, `EmptyState`,
  `ErrorState`, and **`CountUp`** (reduced-motion-aware animated counter).
- **`RiskGauge.tsx`** — semicircular 0–100 risk gauge (animated `stroke-dasharray`).
- **`ExplainDecision.tsx`** — the on-demand "Explain this decision" control
  (Feature A); calls `api.explain`, shows the text with an honest "AI-generated" vs
  "Auto-generated" label from `source`.
- **`governance/ModelFeedbackPanel.tsx`** — the "Model feedback loop" panel
  (Feature B): pending-correction count, Retrain (polls while running), candidate
  metrics vs live, and Promote (disabled/needs-override when the regression guard trips).
- **`lab/PhoneFrame.tsx`** — the phone-style UPI payment composer (sender select,
  amount, receiver autocomplete, QR deep-link, pay button).
- **`lab/PipelineVisualizer.tsx`** — animated per-stage pipeline reveal from a
  `UpiPayResult` snapshot; `StageDetail` renders each stage's data.
- **`lab/ScenarioPanel.tsx`** — the grid of preset attack scenarios with run buttons.
- **`landing/SmoothScroll.tsx`** — Lenis inertia smooth-scroll wrapper (landing only;
  disabled for reduced motion).
- **`landing/BlockchainCanvas.tsx`** — lazy, in-view-only, reduced-motion-aware
  wrapper that mounts the 3D scene (`dynamic(..., { ssr:false })` + IntersectionObserver).
- **`landing/BlockchainScene.tsx`** — the React Three Fiber scene: blocks as
  connected nodes with a travelling "mining" pulse and slow auto-rotation.

## `app/` (routes)
- **`layout.tsx`** — root layout; self-hosted Inter via `next/font/local`,
  `AuthProvider`, `Toaster`.
- **`page.tsx`** — the **public landing page**: hero + live risk gauge + 3D chain,
  scroll-driven pipeline explainer, governance/watchdog section, resilience strip,
  tech stack + footer. Internal `Reveal`, `LiveGauge`.
- **`auth/page.tsx`** — login/register with risk-based step-up OTP; redirects to
  `/dashboard` on success.
- **`(app)/layout.tsx`** — wraps authenticated routes in `AppShell`.
- **`(app)/dashboard/page.tsx`** — the fraud-monitoring dashboard (KPIs with
  `CountUp`, risk histogram, live alerts, daily volume, recent transactions).
- **`(app)/lab/page.tsx`** — the UPI Transaction Lab (manual payment, preset
  scenarios, rapid-fire, guided demo, session history). Reachable without login.
- **`(app)/analyze/page.tsx`** — single-transaction analysis form + full result view.
- **`(app)/blockchain/page.tsx`** — blockchain explorer (chain, validation, blocks).
- **`(app)/analytics/page.tsx`** — deeper analytics charts + model metrics.
- **`(app)/governance/page.tsx`** — governance console (council, proposals, voting,
  integrity/tamper demo, watchdog).
- **`(app)/settings/page.tsx`** — account/settings view.
