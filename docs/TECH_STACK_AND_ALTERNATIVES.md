# SecureFlow — Tech Stack & Alternatives

For each significant technology choice: **what it does here**, **why it's
reasonable for this project**, and **concrete alternatives with honest
tradeoffs**. The recurring constraints are: solo developer, portfolio/interview
context, free-tier hosting, and everything must be explainable in an interview.

---

## FastAPI (backend web framework)

**Here**: serves the REST API, WebSocket, dependency-injected auth/rate-limiting,
Pydantic request/response validation, and auto-generated OpenAPI docs at `/docs`.

**Why reasonable**: async-native (needed for the WebSocket alert stream and the
background watchdog), Pydantic validation removes a whole class of input bugs, and
the DI system (`Depends`) made the access-control work — `require_staff`,
`gov_access` — clean and testable. Minimal boilerplate for a solo dev.

**Alternatives**:
- **Flask** — simpler and more familiar, huge ecosystem. Better when you want
  maximum flexibility and don't need async or built-in validation. Worse here: no
  first-class async, no built-in schema validation, WebSockets need an extension.
- **Django REST Framework** — batteries included (admin, ORM, auth, migrations).
  The better call if this were a large CRUD product with many models and a team,
  or if you wanted the Django admin for free. Overkill here: heavyweight, opinionated,
  sync-first, and the admin/ORM coupling fights a custom pipeline design.
- **Express/Node** — one language across front and back, massive ecosystem. Better
  if the team is JS-only or you want to share types end-to-end. Worse for this
  project: the ML stack is Python (scikit-learn), so Node would force a second
  service or a Python sidecar just for inference.

---

## SQLAlchemy 2.0 + Alembic (ORM & migrations)

**Here**: all persistence — users, transactions, audit logs, governance
proposals/votes, and (in production) the blockchain blocks table — via the typed
2.0 `Mapped[...]` style. One `DATABASE_URL` switches SQLite↔Postgres.

**Why reasonable**: the 2.0 typed API gives IDE/type-checker support; the same
models work on SQLite (dev/tests) and Postgres (prod); Alembic handles schema
evolution. Portable, mature, no vendor lock-in.

**Alternatives**:
- **Raw SQL (psycopg/sqlite3)** — full control, no abstraction cost, easiest to
  reason about performance. Better for a tiny app or hot paths that need
  hand-tuned queries. Worse here: you re-implement identity mapping, relationship
  loading, and dialect portability by hand.
- **Prisma** — excellent DX and type-safety, but it's JS/TS-first; using it from
  Python is awkward. The right call in a Node stack, not this one.
- **Django ORM** — very productive with migrations built in, but it's coupled to
  Django. Choosing it would mean choosing Django.

---

## PostgreSQL (prod) / SQLite (dev & tests)

**Here**: Postgres is the durable store in production (also now holds the audit
chain); SQLite is a zero-setup file DB for local dev and the test suite (an
isolated temp DB per test session).

**Why reasonable**: identical SQLAlchemy models across both means "runs on my
machine" matches prod behaviour; SQLite makes `pytest` hermetic and fast with no
running services; Postgres gives real concurrency, JSON columns, and durability in
prod. Free tier on Render.

**Alternatives**:
- **One DB everywhere (Postgres in dev too)** — eliminates the dev/prod dialect
  gap entirely (the "correct" choice for a team). Cost here: every contributor and
  CI run needs a Postgres instance; slower, more setup. For a solo portfolio the
  SQLite-dev tradeoff is worth it — but note the one real gap it hides is
  concurrency semantics.
- **MySQL/MariaDB** — comparable to Postgres; fine choice. Postgres wins here for
  richer JSON support (used by the audit-log metadata and blocks table) and
  stricter SQL semantics.
- **MongoDB** — schemaless, easy to start. Wrong fit here: the data is highly
  relational (users→transactions→audit logs, proposals→votes with a unique
  constraint), and consensus/governance needs transactional integrity that a
  document store makes harder.

---

## Redis (cache / rate-limit / velocity / geo / pub-sub)

**Here**: JSON caching (dashboard, risk profiles, ML predictions), fixed-window
rate limiting, per-user velocity (sorted sets of event timestamps), last-known geo,
known-device sets, step-up session storage, and the pub/sub bus that fans fraud
alerts out to WebSocket clients. **Every call is fail-open** (`RedisClient._safe`):
a Redis outage degrades to slower-but-correct behaviour using Postgres.

**Why reasonable**: one dependency covers caching, rate-limiting, sliding-window
velocity, and real-time fan-out. Sorted sets are a natural fit for velocity
windows; pub/sub is a natural fit for alert fan-out across processes.

**Alternatives**:
- **Memcached** — simpler, slightly faster pure cache. Worse here: no sorted sets
  (velocity windows), no pub/sub (alert bus), no persistence — I'd need Redis
  anyway for those.
- **In-process caching (e.g. `functools`/`cachetools`)** — zero infra, lowest
  latency. Fine for a single instance, but it can't do cross-process rate limiting
  or pub/sub, and cache/velocity state is lost on restart and not shared across
  replicas. It's exactly what the fail-open path degrades *toward* — acceptable
  temporarily, not as the design.
- **RabbitMQ / Kafka for the alert fan-out** — proper durable messaging with
  consumer groups and replay. The right call at real scale or when alerts must not
  be lost. Overkill here: alerts are ephemeral UI notifications; Redis pub/sub is
  fire-and-forget and that's acceptable, and Kafka on a free tier is impractical.

---

## PyJWT + bcrypt (hand-rolled auth)

**Here**: bcrypt password hashing (`app/core/security.py`), short-lived JWT access
tokens + a long-lived httpOnly refresh cookie, risk-scored login with step-up OTP.

**Why reasonable**: demonstrates that I understand the mechanics (hashing, token
signing/expiry, refresh rotation, step-up) rather than outsourcing them — which is
the point in an interview context. No external dependency or cost.

**Alternatives**:
- **Hosted auth (Auth0 / Clerk / Supabase Auth)** — offloads security-critical code,
  gives SSO/MFA/password-reset for free. The right call for a real product where you
  don't want to own auth risk. Wrong for a portfolio piece meant to *show* the
  mechanics, and it adds a vendor + cost.
- **Session-cookie auth (server-side sessions)** — simpler revocation (delete the
  session), no token-expiry juggling. Better for a classic server-rendered app.
  Here the SPA + separate API + WebSocket favour a stateless bearer token (the WS
  handshake takes the token as a query param). SecureFlow actually uses a hybrid:
  stateless JWT access token + a stateful refresh cookie.
- **Argon2 instead of bcrypt** — Argon2id is the current password-hashing
  recommendation (memory-hard). A reasonable upgrade; bcrypt was chosen for
  ubiquity and to sidestep a known passlib/bcrypt 4.x incompatibility. Both are
  acceptable; Argon2 is the "if I were doing it again" answer.

---

## Custom SHA-256 proof-of-work blockchain (audit trail)

**Here**: every scored transaction (and every governance override / rollback) is
sealed into an append-only, hash-linked, PoW-mined chain
(`app/core/blockchain.py`). The chain is the **source of truth** for tamper
detection and the governance watchdog's auto-rollback.

**Why reasonable — and the honest limits**: it's a genuinely tamper-*evident*
append-only log with an independent integrity check, and it makes a great demo/talking
point. But be honest: this is a **single-writer, single-node** chain. Proof-of-work
here buys almost nothing security-wise (there's no adversarial mining, no
distributed consensus) — its real value is illustrative. A plain hash-chained
table would give the same tamper-evidence with far less code.

**Alternatives**:
- **A hash-chained append-only DB table** (each row stores `prev_hash`) — same
  tamper-evidence, no mining, trivially queryable, transactional with the rest of
  the data. This is what I'd use if the goal were purely a tamper-evident audit log.
- **DB-level audit logging / triggers** — simplest of all; the DB records changes.
  Tamper-evident only insofar as you trust the DB admin — which is exactly the
  threat the governance watchdog is designed to catch, so a trigger alone doesn't
  cover the "rogue admin edits the row" scenario the demo showcases.
- **A real distributed ledger (Hyperledger Fabric)** — actual multi-party consensus
  and Byzantine fault tolerance. The right answer if multiple mutually-distrusting
  banks were co-writing the ledger. Massive operational overhead and completely
  unjustified for a single-service demo.

---

## RandomForest + IsolationForest (scikit-learn)

**Here**: a supervised RandomForest produces a fraud probability; an unsupervised
IsolationForest produces an anomaly score. Both feed the composite risk engine as
**advisory** signals (40% + 15% of the score), not the sole authority.

**Why reasonable**: RandomForest is strong on tabular data, needs little tuning,
and gives feature importances (used for the "top risk drivers" UI). IsolationForest
catches novel/anomalous patterns the supervised model never saw labelled. Both are
fast enough for per-request inference and trivial to ship as a joblib bundle.

**Alternatives**:
- **Gradient boosting (XGBoost/LightGBM)** — usually a few points better on tabular
  fraud data and still gives importances. The likely production upgrade; not used
  here to avoid a heavier dependency and keep training fast/explainable on free-tier
  build minutes.
- **A neural network** — can model richer interactions and sequence/graph structure
  (e.g. transaction graphs). Overkill for this feature set, needs far more data and
  tuning, and is harder to explain — poor fit for a small synthetic tabular dataset.
- **Rules-only, no ML** — fully interpretable and is exactly the fallback heuristic
  (`ModelService._heuristic`). Simpler and sometimes competitive, but can't learn
  non-obvious combinations and needs constant manual threshold tuning. The ML layer
  is what makes "advisory, not authoritative" a meaningful design point.

---

## WebSockets (live alerts)

**Here**: `/ws/alerts` streams HIGH-risk alerts and integrity auto-heals to the
dashboard; the frontend uses one shared, ref-counted socket.

**Why reasonable**: alerts are genuinely push (server-initiated, low-latency), and
a persistent socket avoids polling overhead. Pairs naturally with Redis pub/sub for
multi-process fan-out.

**Alternatives**:
- **Server-Sent Events (SSE)** — simpler, auto-reconnect built in, works over plain
  HTTP. A great fit since alerts are one-directional server→client. The main reason
  for WS here is demonstrating the bidirectional-capable path and Redis-bridged
  fan-out; SSE would be a perfectly valid, arguably simpler choice.
- **Polling** — dead simple, no persistent connections, trivially cacheable. Fine
  for low-urgency data (the dashboard already polls KPIs every 6s). Worse for
  alerts: added latency and wasted requests for events that are usually absent.

---

## Next.js 16 (App Router) + React 19

**Here**: the entire frontend — the public landing page (SSG), the auth-gated
dashboard app, and the public Lab — with the App Router, React Server/Client
components, `next/font/local`, and `next/dynamic` for the lazy 3D scene.

**Why reasonable**: file-based routing + route groups (`(app)`) cleanly separate
the public marketing page from the auth-gated app; SSG gives the landing page a fast
first paint; Vercel deployment is one click. React 19 + the compiler reduce manual
memoization.

**Alternatives**:
- **Vite + React SPA** — faster/simpler dev, no SSR machinery. Good if you don't
  need SSG/SSR or file routing. Here the landing page benefits from static
  generation and the routing model is convenient; a pure SPA would need a separate
  router and lose SSG.
- **Remix** — excellent data-loading and web-standards story. A strong alternative;
  Next was chosen for the Vercel integration and the maturity of its App Router +
  `next/font`/`next/dynamic` ergonomics.
- **Server-rendered templates (Jinja from FastAPI)** — no separate frontend build,
  simplest deploy. Wrong fit for a rich, interactive, real-time dashboard with 3D
  and live sockets.

---

## Zustand (state) — *scope check*

**Here**: `zustand` is listed in `package.json`. In practice the app leans on React
context (`AuthProvider`), local component state, and a shared external-store hook
(`useAlertStream` via `useSyncExternalStore`) rather than a large global store.

**Why reasonable**: the app doesn't have much cross-cutting client state, so a heavy
store isn't needed; a context for auth + a shared socket hook covers it.

**Alternatives**:
- **React Context** — zero dependency, already used for auth. Best when state is
  small and changes infrequently; can cause broad re-renders if overused for
  high-frequency updates (which is why the alert stream uses `useSyncExternalStore`
  instead).
- **Redux Toolkit** — structure, devtools, middleware. Worth it for large apps with
  complex, shared, debuggable state. Overkill here.
- **Jotai/Recoil** — atomic, fine-grained reactivity. A good middle ground for
  medium apps; unnecessary for this amount of state.

---

## Tailwind CSS v4

**Here**: all styling, plus a small set of design tokens (CSS custom properties in
`globals.css`) and a few reusable component classes (`.panel`, `.btn`, `.terminal`).

**Why reasonable**: fast to build a consistent dark security-themed UI, tokens keep
the palette centralized, and utility classes keep styles colocated with markup.

**Alternatives**:
- **CSS Modules** — scoped, no utility-class verbosity, plain CSS. Better if you
  prefer semantic class names and less markup noise. Slower to iterate on a design
  system.
- **styled-components / Emotion** — dynamic, prop-driven styles in JS. Nice for
  highly dynamic theming; adds runtime cost and, with RSC, friction. Tailwind is
  zero-runtime.
- **Plain CSS** — no build/tooling, total control. Fine for a small site; scales
  poorly for consistency across many components.

---

## Recharts (dashboard charts)

**Here**: the risk-score histogram, daily-volume line, and analytics charts.

**Why reasonable**: React-native component API, sensible defaults, good enough
customization for a dashboard, quick to wire up.

**Alternatives**:
- **D3 directly** — unlimited control, best for bespoke/novel visualizations. Far
  more code for standard bar/line charts; overkill here.
- **Chart.js** — canvas-based, performant for large datasets, but imperative and
  less React-idiomatic.
- **Nivo / Victory** — also React-first. Nivo is prettier out of the box but
  heavier; Victory is flexible but more verbose. Recharts hit the simplicity sweet
  spot for this dashboard.

---

## Framer Motion + React Three Fiber (landing animation & 3D)

**Here**: Framer Motion drives all 2D micro-interactions, section scroll-reveals,
the risk-gauge cycle, and the mobile drawer; React Three Fiber renders the lazy,
in-view-only 3D blockchain node graph on the landing page. Lenis adds inertia
smooth-scroll on the landing page only. All respect `prefers-reduced-motion`.

**Why reasonable**: Framer Motion is already a dependency and is declarative and
accessibility-aware (`useReducedMotion`); R3F gives thin React bindings to Three.js
so the one purposeful 3D element stays componentized and lazy-loaded (never blocks
first paint, never runs for reduced-motion users).

**Alternatives**:
- **GSAP** — the most powerful timeline/scroll animation library. Better for complex
  choreographed sequences; heavier and imperative, and Framer Motion already covers
  the needs here with a React-native API.
- **Plain CSS animations** — zero JS, best performance for simple effects (used here
  for the glow line and shimmer). Can't easily do scroll-linked reveals or 3D.
- **react-spring** — physics-based, composes well with R3F. A fine alternative to
  Framer Motion; Framer was chosen because it was already present and its
  `whileInView` + `useReducedMotion` ergonomics fit the scroll-reveal needs.

---

## Render (backend) + Vercel (frontend)

**Here**: FastAPI + managed Postgres + managed Redis on Render (`render.yaml`);
Next.js on Vercel (`frontend/vercel.json`). The audit chain persists to Postgres in
prod (`BLOCKCHAIN_STORAGE=db`) so it survives redeploys on the free tier.

**Why reasonable**: both have generous free tiers and one-click blueprint/Git
deploys; Vercel is the native home for Next.js; Render's managed Postgres+Redis
means no infra to run. Perfect for a solo portfolio.

**Alternatives**:
- **Single provider (Railway / Fly.io)** — everything (app + DB + Redis) in one
  place, simpler mental model and networking. The main reason for the split is that
  Vercel is the best Next.js host; a single provider would trade that for
  consolidation. Fly.io also gives real persistent volumes if you preferred a disk
  over DB-backed chain storage.
- **Self-hosted VPS + Docker** — cheapest at scale, full control (the repo ships a
  `docker-compose.yml` that runs the whole stack). Worse for a portfolio: you own
  uptime, TLS, backups, and deploys.
- **AWS/GCP** — infinitely scalable and the "real production" answer. Massive
  overkill and cost/complexity for a demo; the free tiers are fiddlier than
  Render/Vercel.

---

## Groq (LLM for "Explain This Decision") — the one external cost

**Here**: the explain endpoint turns the already-computed risk signals into 2–3
plain-English sentences via the Groq API, using **Llama 3.1 8B Instant** (a
small/fast/inexpensive model served on Groq's LPU inference) for a short
structured completion. The LLM only *explains* a decision the risk engine
already made — it never influences the score, tier, or action.

**Why reasonable — and the honest cost note**: this is the **one feature in the
project with an external, per-call cost dependency**. Everything else runs on
free-tier infra with no marginal cost. The cost is deliberately bounded and kept
close to zero: it's **on-demand only** (a button, not automatic), **cached in
Redis per transaction** (repeat clicks are free), **rate-limited more tightly**
than any other endpoint (10/window vs 60), uses the **cheapest model** with a low
`max_tokens` (~220), and has a **hard 5s timeout with no retries**. And it
**degrades to a deterministic template** when the key is absent or the call
fails — so the app is fully functional with zero configuration and zero cost.
Groq's free tier and very low per-token latency make it a good fit for an
on-demand, latency-sensitive call like this one.

**Alternatives**:
- **A hosted LLM from another provider (Anthropic, OpenAI, Google Gemini, etc.)** —
  comparable capability for a task this small. Any of them would work; the
  tradeoff is provider lock-in, API shape, and cost, not capability. Groq was
  chosen for its generous free tier and fast inference on small open models, and
  the fallback-first design makes the provider easily swappable.
- **A local/open-source model (Llama, Mistral via Ollama)** — no per-call cost and
  full data control. The better call if the explanations must never leave your
  infra or you want zero marginal cost — but it needs a GPU/host to run, which
  defeats the free-tier constraint here. The deterministic template is effectively
  the zero-cost local fallback.
- **No LLM — a richer rules-based template only** — zero cost, fully deterministic,
  no external dependency (this is exactly the fallback path). It's honestly *good
  enough* for most explanations; the LLM buys more natural phrasing and the ability
  to weave several signals into a sentence. For a system that must be free and
  offline, drop the LLM and keep only the template.

## Governance → model feedback loop: versioned + manually promoted (Feature B)

**Here**: when the council unanimously approves overturning a decision, that
correction becomes labeled training data (keyed to the exact feature vector scored
at the time). An admin can retrain a **separately versioned candidate** model from
those corrections plus the synthetic dataset; a **regression guard** blocks
promoting a worse candidate; nothing is **ever auto-promoted**.

**Why reasonable**: the corrections are few, human-verified, and high-stakes
(they change how fraud is scored), so the pipeline is built around *not trusting
them blindly*: weight them above synthetic data but never let them silently
degrade the model, keep every candidate as an immutable versioned artifact, and
require an explicit human promotion behind a metric guard. It closes the loop
between the governance system and the ML model without introducing a way to
quietly poison the model.

**Alternatives**:
- **Online / incremental learning** (update the live model as corrections arrive) —
  adapts fastest. Wrong here: it makes the live model a moving target with no
  reviewable artifact, and a handful of mislabeled or adversarial corrections could
  quietly corrupt production with no gate. Versioned-and-promoted trades adaptation
  speed for safety and auditability, which is the right trade for fraud scoring.
- **Just discard governance corrections** (what the system did before Feature B) —
  simplest; the correction updates the transaction and the chain, then the training
  signal is thrown away. Perfectly fine if you don't want a feedback loop at all —
  but it wastes genuinely valuable human-labeled data.
- **A separate human-in-the-loop labeling/MLOps platform** (e.g. a feature store +
  a training pipeline in Airflow/Kubeflow, model registry, CI-gated promotion) — the
  "real" production answer. Massive overkill for a solo portfolio project; Feature B
  is a deliberately minimal, self-contained version of that same shape (feature
  snapshot → labeled corrections → versioned candidate → guarded manual promotion).
- **Note on why features are snapshotted, not recomputed**: velocity, geo-history,
  and new-device features are time- and state-dependent. Recomputing them after the
  fact from current Redis/DB state would not match what the model actually scored, so
  training on a drifted vector would quietly corrupt the model. The loop therefore
  only uses transactions with a persisted `feature_snapshot` (scored after the
  feature shipped) and never backfills historical transactions.

## Notable design decision: WebSocket authentication

The live alert feed carries real transaction PII (VPAs, amounts, risk scores). The
original implementation accepted a missing/invalid token as an "anonymous read-only"
connection, which leaked every user's fraud alerts to anyone who opened the socket.
This was fixed to **require a valid access token** (`?token=`) and reject
missing/invalid tokens with close code 1008 before accepting the connection. A
public, PII-redacted feed was considered for the demo but rejected: the Lab already
provides a rich unauthenticated demo, so there was no product reason to expose a
second unauthenticated data surface.
