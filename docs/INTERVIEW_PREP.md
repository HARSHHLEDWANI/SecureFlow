# SecureFlow — Interview Prep

55 realistic interview questions with model answers, grounded in the actual
codebase. Answers are written to be spoken in ~60–90 seconds.

---

## System design & architecture

**Q: Give me the 30-second overview of SecureFlow.**
A: SecureFlow is a real-time fraud-detection system for UPI payments. Every
transaction is scored 0–100 by blending a machine-learning model (RandomForest +
IsolationForest) with rule-based signals like velocity, impossible-travel geo
checks, new-device/new-beneficiary, and amount anomaly. Based on the score it takes
a tiered action — LOW allows, MEDIUM triggers a step-up OTP, HIGH blocks — and seals
the result into a custom SHA-256 proof-of-work blockchain as an immutable audit
record. It's a FastAPI + Postgres + Redis backend with a Next.js frontend, plus a
multi-admin governance layer and a self-healing integrity watchdog.

**Q: Why a monolith instead of microservices?**
A: It's a solo project where the components are tightly coupled around one
pipeline, so a monolith keeps everything transactional and simple to deploy on a
free tier. There's no independent-scaling or separate-team pressure that would
justify the operational cost of microservices. That said, the code is factored so
the seams are obvious: the ML model, Redis client, and blockchain are all singletons
behind clean interfaces, so the model or the alert bus could be extracted into a
service later with minimal churn.

**Q: Walk me through the transaction pipeline.**
A: It lives in `app/core/pipeline.py::run_pipeline` and is the single source of
truth. First `gather_signals` assembles raw signals — velocity from Redis sorted
sets, geo-velocity from last-known location, new-device from a Redis set, amount
stats — each with a Postgres fallback. Then `predict_cached` runs the ML model
(cached in Redis). `compute_risk` blends the ML outputs with rule signals into a
0–100 score and a tier. We persist the `Transaction`, mine a blockchain block
recording the governed state, write an `AuditLog`, update Redis history, and if the
tier is HIGH we dispatch a live alert over the WebSocket.

**Q: What's the single source of truth for a transaction's state?**
A: There are two layers, deliberately. The Postgres `Transaction` row is the live
operational state. The blockchain is the *immutable checkpoint* — every analyze and
every governance override writes the governed fields (status, tier, score) into a
block. When they disagree, the chain wins: that's exactly what the integrity
watchdog uses to detect and roll back tampering. So Postgres is what the app reads,
but the chain is the authority for "what did we actually decide."

**Q: The same `run_pipeline` serves both the live API and the demo Lab. Why?**
A: So the Lab is a genuine demo, not a mock. The only thing that differs is how the
input signals are built — the Lab can inject deterministic overrides for
reproducible attack scenarios — but the model, scoring, persistence, chain, and
alerting are literally the same code path. That means Lab transactions show up in
the dashboard and analytics like any other, and I can trust the demo reflects real
behaviour.

**Q: How would you scale this to real UPI volume (millions of tx/sec)?**
A: Several things break first, so I'd tackle them in order. The blockchain mining is
synchronous in the request path — I'd move audit-logging to an async queue and batch
blocks. The single Postgres becomes the bottleneck next — I'd shard by user, add
read replicas for analytics, and move the dashboard aggregation to a
precomputed/materialized store instead of scanning all transactions. The model would
move to a dedicated inference service with batching. Redis is already horizontally
scalable. And I'd replace the in-process WebSocket fan-out with a proper broker.

**Q: What breaks first under load, concretely?**
A: The analytics dashboard endpoint — it currently loads *all* transactions into
Python to compute KPIs (`select(Transaction)` with no aggregation pushdown). It's
Redis-cached for 60s so it's fine at demo scale, but it's O(n) memory and would fall
over first. The fix is DB-side aggregation and a rolling summary table.

**Q: Why is mining a block inside the request a problem, and why is it OK here?**
A: Proof-of-work brute-forces a nonce until the hash has N leading zeroes, which is
unbounded CPU on the hot path. At difficulty 2 it's a few milliseconds, so it's fine
for a demo. In production I'd never do CPU-bound work synchronously in a request —
I'd append to a queue and mine asynchronously, accepting slightly delayed audit
sealing.

---

## Security

**Q: You found an access-control vulnerability in this codebase. Describe it.**
A: `require_role` was defined but never actually used — it was dead code. As a
result, any authenticated user, including a low-privilege VIEWER, could list *every*
user's transactions and VPAs, read any user's risk profile by id, and read the full
fraud dashboard, analytics, and blockchain. It was a broken-access-control /
IDOR-class bug: authentication was enforced, but authorization wasn't. The
governance routes were correctly gated with a custom `gov_access` dependency, but
the transaction/analytics/blockchain routes weren't.

**Q: How did you fix it?**
A: I introduced real authorization. I added `require_staff` (ANALYST/ADMIN) and gated
the analytics and blockchain routers with it, since those are aggregate fraud-ops
views. For the transaction routes I added ownership checks via `is_staff`: a VIEWER
only sees their own transactions and risk profile, while ANALYST/ADMIN keep full
visibility because it's a fraud-ops tool. Cross-user reads by a VIEWER return 404,
not 403, so we don't leak that another user's transaction id exists. And I added
tests for both the allow and deny paths.

**Q: There was also a WebSocket auth bug. What was it?**
A: The alert socket took an optional `?token=` param, but if the token was missing
or failed to decode it just `pass`ed and connected you anyway as "anonymous
read-only." So anyone could open `/ws/alerts` with no token and receive the live
feed of every fraud alert — amounts, VPAs, risk scores. I changed it to require a
valid token and reject missing/invalid ones with close code 1008 before accepting
the connection. There's no anonymous feed; the Lab already covers the
unauthenticated demo need.

**Q: JWT vs session cookies — what did you choose and why?**
A: A hybrid. The access token is a short-lived stateless JWT sent as a Bearer token —
that suits a separate SPA and, importantly, the WebSocket handshake, which can't set
an Authorization header so it takes the token as a query param. The refresh token is
a stateful httpOnly cookie, which gives me easy rotation and keeps the long-lived
secret out of JavaScript. So I get stateless request auth plus a revocable refresh
path.

**Q: How are passwords stored?**
A: bcrypt hashes with per-password salts, via the `bcrypt` library directly in
`app/core/security.py`. I used bcrypt rather than passlib to avoid a known
passlib/bcrypt 4.x incompatibility. Verification is constant-time via
`bcrypt.checkpw`. If I were hardening for production I'd move to Argon2id, which is
the current memory-hard recommendation.

**Q: The demo/Lab endpoints are unauthenticated. Isn't that a risk?**
A: It's a deliberate, scoped decision. The `/upi/*` endpoints only ever act on seeded
demo users (`@secureflow.local`), never on real accounts — the simulator resolves the
sender against a fixed demo roster and 422s anything else. So the blast radius is
limited to throwaway demo data, and it's rate-limited. The demo password and OTP
being returned by the API are also intentional demo affordances, clearly labelled as
such. I document these as intentional rather than leaving them silently present.

**Q: What would you change before this could touch real money?**
A: A lot, and I'm upfront about it. Real out-of-band OTP delivery instead of
returning it; Argon2 hashing; per-user rate limiting and abuse detection; secrets in
a real vault; the ML model validated against real labelled transaction data with
proper drift monitoring; the blockchain either dropped for a simpler signed audit
log or backed by real infrastructure; and a full authz audit with least-privilege
everywhere. It's a portfolio system that demonstrates the mechanics, not a certified
fintech product — and I'd rather say that than overclaim.

**Q: How does the login risk-scoring work?**
A: Login itself is scored in `_assess_login_risk` — unrecognised device (+45), odd
hour (+20), and a missing device fingerprint (+10). LOW logs in directly, MEDIUM
forces a step-up OTP challenge stored in Redis with a short TTL, and HIGH is blocked
outright. It's a lightweight version of the same risk-based philosophy the
transaction pipeline uses.

---

## Machine learning

**Q: Why RandomForest and IsolationForest together?**
A: They cover different failure modes. The RandomForest is supervised — it learns
the labelled fraud patterns and gives me a probability plus feature importances,
which I surface as "top risk drivers." The IsolationForest is unsupervised — it flags
anomalous transactions that don't look like anything it was trained on, catching
novel fraud the supervised model would miss. Blending a "have I seen this labelled"
signal with a "does this look weird at all" signal is more robust than either alone.

**Q: How are features engineered, and why is the same function used for training and inference?**
A: `extract_features` in `app/ml/features.py` turns raw signals into the numeric
vector — amount/log/z-score, transaction-type one-hots, hour/night/weekend, velocity
windows, geo distance and an impossible-travel flag, new-device/new-beneficiary. The
key discipline is that both training and live inference call the *exact same*
function. If training and serving computed features differently — training/serving
skew — the model would silently degrade in production. One shared function makes that
class of bug impossible.

**Q: How does the synthetic dataset avoid being trivially separable?**
A: Two ways. First, fraud labels come from independent latent *behaviours* — account
takeover, scam payments, impossible travel, micro-testing — not from thresholding the
features. So the model has to learn the patterns rather than re-derive a rule I baked
in. Second, I inject label noise: about 10% of frauds are made to look benign
("stealthy fraud") and some legit transactions look unusual. That forces the model to
generalize instead of memorizing a clean boundary, and it's why the test AUC is
~0.95, not a suspicious 1.0.

**Q: What does the AUC-ROC actually mean here, and what are its limits?**
A: AUC ~0.95 means that if you pick a random fraud and a random legit transaction,
the model ranks the fraud as riskier about 95% of the time. Its limit is that it's
threshold-independent and computed on *synthetic* data — it tells me the model
separates the classes I generated, not that it'd work on real UPI fraud. On a highly
imbalanced real problem I'd care more about precision/recall at the operating
threshold and the cost of false positives than about AUC.

**Q: What does "advisory, not authoritative" mean for the ML model?**
A: The model never decides on its own. In `compute_risk`, ML fraud probability is 40%
of the score and the anomaly score is 15% — the remaining 45% is deterministic rule
signals. So a confident model can't single-handedly block a payment, and if the model
is wrong or unavailable, the rules still produce a sensible score. It also means the
decision is explainable: I can always point to the weighted components. There's even a
heuristic fallback if no trained model is loaded at all.

**Q: How would you validate this against real transaction data?**
A: I'd start with a backtest on labelled historical data, measuring precision/recall
at the intended operating point and the dollar-weighted cost of false negatives vs the
friction cost of false positives. Then a champion/challenger or shadow deployment
where the model scores live traffic without acting, to compare against the current
system. And ongoing drift monitoring on both feature distributions and outcome rates,
because fraud patterns move.

**Q: How is model training kept out of the request path and the test suite?**
A: Training is an offline step — `python -m app.ml.training` does a 5-fold
grid-searched RandomForest and writes a joblib bundle, run at build/deploy time. The
app just loads that bundle once via a singleton. For tests I added a fast path
(`run_training(fast=True)`) that skips grid search with fixed hyperparameters, so a
fresh clone auto-trains a real model in a few seconds instead of ~30.

---

## The blockchain component

**Q: What problem does the blockchain actually solve that a simple audit table doesn't?**
A: Honestly, less than the name suggests — and I lead with that. Its real value is
tamper-*evidence*: because each block hashes its contents and links the previous
hash, you can't quietly edit a past record without breaking the chain, and the
governance watchdog uses that to detect and auto-revert direct DB tampering. A plain
audit table can be edited by anyone with DB access without leaving a detectable trace.
That said, a hash-chained append-only table would give the same tamper-evidence with
far less code — the full PoW "blockchain" is partly a demonstration piece, and I'm
clear about that.

**Q: How do proof-of-work and difficulty work here?**
A: `_mine` brute-forces a `nonce` until the block's SHA-256 hash starts with N zeroes,
where N is the difficulty (2 in the demo). Validation re-hashes each block, checks the
leading-zero requirement, and checks that each block's `previous_hash` matches its
parent. Changing any past block's content changes its hash, which breaks the link and
fails the PoW check.

**Q: What does tamper detection actually check?**
A: `tamper_detection` walks the chain and returns the index of the first block whose
stored hash doesn't match a recompute, or whose `previous_hash` doesn't match the
prior block. That catches edits to block contents. Separately, the governance
`verify_integrity` compares the live DB transaction against the newest on-chain
governed state for that transaction — that catches someone editing the *database row*
while the chain is intact.

**Q: What are the honest limits of a single-node "blockchain"?**
A: It's single-writer and single-node, so proof-of-work buys essentially no security
here — there's no adversarial mining and no distributed consensus to protect against.
Anyone who can rewrite the whole chain file *and* is willing to re-mine it could forge
it; the DB-backed storage and the watchdog mitigate that but don't make it a real
distributed ledger. Its value is a tamper-evident, independently-verifiable audit log,
not Byzantine fault tolerance.

**Q: Why did you move blockchain storage from a JSON file to Postgres?**
A: On Render's free tier the container filesystem isn't guaranteed to survive
redeploys, so a file-based chain could silently reset to genesis — which would destroy
the headline "immutable audit trail." I made storage pluggable: `file` for dev/tests
(fast, zero-dependency) and `db` for production, which appends blocks to a
`chain_blocks` table in the already-persistent Postgres. The in-memory hashing and
tamper logic are identical; only persistence changes. A Render persistent disk was the
alternative but it requires a paid plan, so the DB backend keeps the free tier.

---

## Governance & consensus

**Q: Why require unanimous approval to reverse a decision?**
A: Reversing a fraud decision — say unblocking a blocked payment — is the single most
dangerous admin action, because one compromised or malicious admin could quietly wave
through fraud. Requiring unanimous approval from a 4-admin council means no single
admin can do it; it takes collusion of the entire council. It's the
separation-of-duties principle applied to the most sensitive operation.

**Q: How does divergence detection work?**
A: When a proposal is created it snapshots the transaction's governed state as a hash.
Every vote independently re-computes and attests that hash. If the record changed
between the proposal and any vote — someone tampered with it mid-vote — the attested
hash won't match, the proposal is flagged DIVERGED and the change is discarded rather
than applied to a record that's no longer what people agreed to review. There's also a
final guard in `_apply` that re-checks the hash before committing.

**Q: What does the watchdog actually do, and how often?**
A: `integrity_watchdog` is a background asyncio loop (every 15s by default). Each cycle
`scan_and_heal_once` walks every chain-anchored transaction, compares the live DB state
to the newest on-chain agreed state, and if they diverge it auto-rolls the DB back to
the chain's value, seals a `GOVERNANCE_AUTOHEAL` block, and emits a live alert. So even
a direct database edit that bypasses consensus gets detected and reverted within
seconds, with the blockchain as the ground truth.

**Q: Two admins vote at the same instant — what happens? Race conditions?**
A: Each vote is its own request with its own DB transaction, and there's a unique
constraint on `(proposal_id, admin_id)` so an admin can't double-vote. Evaluation
happens per-vote: whichever commits reaching unanimous approval triggers `_apply`. The
main residual risk is two final approvals racing to apply — the `_apply` guard
re-checks state and the proposal status transition guards against applying twice, but
under true concurrency I'd want a row-level lock (`SELECT ... FOR UPDATE`) on the
proposal to fully serialize resolution. On SQLite in tests it's serialized anyway;
on Postgres I'd add the lock.

---

## Redis & resilience

**Q: What does "fail-open" vs "fail-closed" mean, and where is each used?**
A: Fail-open means when a dependency is down you allow the operation to proceed;
fail-closed means you deny it. In SecureFlow the Redis wrapper is fail-open
everywhere — if Redis is down, every helper logs once and returns a neutral default,
and the caller recomputes from Postgres. The one deliberately fail-open-toward-allow
spot is rate limiting: if Redis is down, `rate_limit_hit` returns 0, so we allow
rather than lock everyone out. The security-critical decisions (auth, the risk
pipeline) don't depend on Redis for correctness, so failing open there is safe — it's
slower, not wrong.

**Q: What happens end-to-end if Redis is completely down?**
A: The app stays correct, just slower. Velocity and new-device checks fall back to
Postgres counts; geo falls back to the last transaction row; caching is skipped so the
dashboard and risk profiles recompute every time; the step-up OTP session can't be
stored so step-up logins degrade; and alert pub/sub falls back to in-process broadcast
so a single node still gets live alerts. Nothing throws a Redis exception at the user —
that's the whole point of the `_safe` wrapper.

**Q: Why cache velocity/geo in Redis instead of always hitting Postgres?**
A: Velocity is a sliding-window count of recent events per user, which maps perfectly
onto a Redis sorted set — O(log n) inserts and range counts, with automatic expiry —
whereas doing it in Postgres means a `COUNT` with a timestamp filter on every
transaction. Geo and known-device are tiny per-user lookups that would otherwise be
extra queries on the hot path. Redis keeps the per-transaction latency low; Postgres
is the correctness fallback, not the fast path.

**Q: Isn't fail-open on rate limiting a vulnerability?**
A: It's a conscious trade-off. If Redis blips, fail-closed would lock every user out —
a self-inflicted outage — while fail-open briefly removes throttling. For this app the
availability cost of fail-closed outweighs the abuse risk of a short unthrottled
window, especially since the sensitive actions have other guards. In a system where
rate limiting is a security control (e.g. brute-force protection on login), I'd
reconsider and possibly fail-closed on that specific endpoint.

---

## Frontend & UX

**Q: What's your frontend state-management approach and why?**
A: I kept it deliberately light. Auth is a React context (`AuthProvider`); most state
is local component state. The one cross-cutting piece is the live alert stream, which
I built as a shared, ref-counted WebSocket exposed via `useSyncExternalStore` — so the
dashboard and the app-shell nav badge share a single socket instead of opening two.
`zustand` is in the dependencies but the app doesn't need a heavy global store, so I
didn't force one in.

**Q: Why WebSockets over polling for alerts?**
A: Alerts are genuinely push — server-initiated, low-latency, and mostly absent — so a
persistent socket is a better fit than polling, which would either add latency or waste
requests. The dashboard KPIs, by contrast, *do* poll every 6s, because they're
periodic aggregate reads where freshness-within-seconds is fine and a socket would be
overkill. So I use each tool where it fits.

**Q: You found a mobile-navigation gap. What was it and how did you fix it?**
A: The sidebar was `hidden md:flex` with no alternative below the `md` breakpoint —
there was literally no hamburger, drawer, or bottom nav, so on a phone you could see a
page but had no way to navigate anywhere except by typing URLs. I added a mobile header
with a hamburger that opens a framer-motion slide-in drawer reusing the same nav array
and the same governance-only filtering, closing on navigation and backdrop tap, and
tested it at 375/768/1024px.

**Q: How did you add 3D without hurting performance or accessibility?**
A: Three guardrails. It's code-split with `next/dynamic({ ssr:false })` so the Three.js
bundle never blocks first paint. It only mounts when scrolled into view via an
IntersectionObserver. And it respects `prefers-reduced-motion` — reduced-motion users
get a static fallback and never load the scene. The scene itself is deliberately
lightweight — nine nodes, no post-processing, capped DPR — so it stays smooth on a
mid-range phone. The core dashboard never depends on the 3D layer loading.

**Q: Why is the landing page separate from the dashboard, and why smooth-scroll only there?**
A: The landing page is a public, static marketing/story page for recruiters — before
my changes a logged-out visitor hit a bare login form with zero context. I moved the
dashboard to `/dashboard` behind auth and made `/` a public landing. I added Lenis
inertia smooth-scroll there because it suits a scroll-driven narrative, but I
deliberately kept the dashboard on native scroll — smooth scroll makes scanning dense
tables feel laggy, so it belongs on the story page, not the data screens.

**Q: Why self-host the font?**
A: The original used `next/font/google` for Inter, which fetches from Google Fonts at
build time. That's fine on Vercel but hard-fails in any network-restricted CI/build
environment. I switched to `next/font/local` with a self-hosted Inter variable woff2,
so the build has zero external network dependency regardless of where it runs.

---

## Testing

**Q: The test suite failed on a fresh clone. What was the bug and how did you fix it *properly*?**
A: Six of the tests failed on a fresh clone because the trained model file is
gitignored and absent, so `ModelService` silently fell back to the interpretable
heuristic, which scores severe attacks lower than the trained model — so the
scenario-decision assertions failed. The lazy fix would be to relax those assertions.
Instead I added an autouse, session-scoped pytest fixture that trains a real model if
one doesn't exist, using a fast path that skips grid search. So a bare `pytest` on a
fresh clone now trains a genuine model in a few seconds and goes green — fixing the
setup, not the tests.

**Q: How is the test suite isolated from a shared dev DB/Redis?**
A: `conftest.py` configures an isolated environment before the app is imported — a
temp SQLite database and a temp chain path per session — and every test runs against
an in-memory `fakeredis` instance injected via monkeypatch, so no real Redis is
needed. The FastAPI `TestClient` runs the real app lifespan, so tables are created and
demo users seeded exactly like production. Tests never touch a developer's real data.

**Q: How do you test the authorization changes?**
A: `test_authz.py` covers both paths with two fixtures — an ANALYST client and a
VIEWER client. Deny-path tests assert a VIEWER gets 403 on analytics and blockchain,
404 on another user's transaction, 403 on another user's risk profile, and an empty
own-scoped listing. Allow-path tests assert an ANALYST can read any user's transaction,
risk profile, analytics, and chain. Testing both the allow and deny paths is the point
— a permission check that only tests the happy path can hide a hole.

**Q: How did you verify the fresh-clone fix actually works rather than just assuming?**
A: I moved the trained model file aside to simulate a genuine fresh clone, ran the
suite, watched the fixture auto-train and all tests pass, confirmed the model was
regenerated, then restored the full grid-search model. I also verified `python -m
app.ml.training` still completes and prints metrics, since I'd refactored it to share
code with the fast path.

**Q: How do you test the WebSocket and the blockchain DB backend?**
A: For the socket, tests mint a valid token and assert a connected client receives a
dispatched alert, plus new tests that missing/invalid tokens are rejected with a
disconnect. For the DB-backed chain, a test clears the `chain_blocks` table, builds a
`Blockchain(storage="db")`, mines blocks, then builds a *fresh* instance and asserts it
reloads the identical chain from the database and still validates — proving durability
and correct reload.

---

## Tradeoffs & self-critique

**Q: What's the biggest weakness of this project?**
A: The blockchain is over-engineered for what it delivers — a hash-chained table would
give the same tamper-evidence with a fraction of the code and no synchronous mining on
the request path. I keep it because it's a strong demo of the concept and pairs well
with the governance/watchdog story, but if I were optimizing purely for engineering
quality I'd simplify it. I'd rather name that honestly than pretend the PoW is doing
security work it isn't.

**Q: What would you do differently if you started over?**
A: I'd wire up authorization from day one instead of leaving `require_role` as dead
code — designing the permission model first would have prevented the access-control gap
entirely. I'd also push the analytics aggregation into the database instead of loading
all transactions into Python, and I'd start the audit log as a simple hash-chained
table and only "upgrade" to a full chain if there were a real reason.

**Q: What did you cut for time?**
A: Real OTP delivery (it's returned in the response for the demo), production-grade
observability (metrics/tracing), pagination on the list endpoints, and a proper
row-lock on concurrent governance resolution. None of them change the architecture —
they're the difference between a portfolio demo and a production system, which I try to
be explicit about.

**Q: How would this fail in production?**
A: The most likely failure is the analytics endpoint OOMing as transaction volume
grows, since it materializes all rows. After that, the synchronous block mining would
add tail latency under load. And the ML model would degrade silently against real
fraud that doesn't resemble my synthetic distribution — without drift monitoring I
wouldn't notice until fraud slipped through. Those are the three I'd instrument and fix
first.

**Q: Why should I trust your risk scores if the data is synthetic?**
A: You shouldn't trust the *numbers* — you should evaluate the *system*. The synthetic
data proves the pipeline learns non-trivial patterns and that features are consistent
between training and serving, but I'm explicit that real validation requires real
labelled data, backtesting, and drift monitoring. The value on display is the
architecture — advisory ML blended with rules, tiered actions, tamper-evident audit,
consensus governance — not a production-calibrated fraud model.

**Q: What part are you most proud of?**
A: The governance-plus-watchdog system. It's the most novel piece: a change is a
proposal not a write, it needs unanimous council approval, every vote attests to the
record's state so mid-vote tampering is caught, and a background watchdog continuously
reconciles the live database against the immutable chain and auto-heals any direct
tampering. It's a coherent answer to "how do you stop a rogue admin," and it ties the
blockchain, the consensus, and the audit trail together into one story.

---

## Rapid-fire / fundamentals

**Q: Why is the ML prediction cached in Redis?**
A: Identical signal sets produce identical predictions, so `predict_cached` keys the
result on a stable hash of the signals (`prediction:{hash}`, 10-min TTL). It avoids
re-running the model for repeated identical inputs — useful in the Lab where the same
scenario runs repeatedly — while still being correct because the key captures all
inputs.

**Q: How is "impossible travel" computed?**
A: In `extract_features`: implied speed = geo distance between consecutive
transactions divided by the time elapsed. If that exceeds 700 km/h — faster than any
ground travel — the `impossible_travel` flag fires, and the risk engine treats it as a
maximal geo signal. It's a simple physical-plausibility check that catches
credential theft from a different city.

**Q: How does the risk engine turn signals into a decision?**
A: `compute_risk` computes seven normalized components (ML fraud, anomaly, velocity,
geo, new-device, amount z-score, time-of-day), multiplies each by a fixed weight
summing to 100, sums them, and clamps to 0–100. Then LOW ≤30 → allow, ≤70 → step-up
OTP, else block. The weighted contributions are returned too, so every decision is
explainable.

**Q: Why does the first registered user become an admin?**
A: Bootstrapping — someone has to be the initial admin on a fresh deployment, and there's
no out-of-band provisioning step in a demo. The registration route counts *real*
users (excluding seeded demo/council accounts) and promotes the first one to ADMIN;
everyone after is a VIEWER. The governance "main admin" is then defined as the oldest
real admin.

**Q: What's the difference between the Lab decisions (APPROVED/STEP_UP/BLOCKED) and the stored status?**
A: They're the same underlying state with demo-friendly labels. The engine stores
`TxnStatus` — ALLOWED/STEP_UP/BLOCKED — and the Lab maps those to APPROVED/STEP_UP/
BLOCKED with emojis for presentation. The governance tests rely on that mapping to
translate a Lab decision back to the stored status.

**Q: How do you keep scenarios repeatable regardless of run order?**
A: Before each preset scenario, `reset_sender_baseline` clears the sender's rolling
velocity in Redis and re-primes their known device and home location. So every
scenario is evaluated against the user's *normal* history, not whatever an earlier
attack scenario left behind. Manual `/upi/pay` calls deliberately skip the reset so
state evolves live — that's how the rapid-fire velocity escalation works.

**Q: Why is there both a `Transaction.block_hash` and an `AuditLog`?**
A: They serve different roles. `block_hash` on the transaction is a pointer to the
immutable chain record of the decision. The `AuditLog` is a richer, queryable
per-action history — including governance actions, rollbacks, and auto-heals — with
metadata like the risk components and before/after states. The chain is the tamper
authority; the audit log is the human-readable trail.

**Q: How does graceful degradation show up to the user?**
A: It mostly doesn't — that's the goal. If Redis is down the app is slower but every
endpoint still returns correct data, the health check reports `redis: false`, and the
live alert feed falls back to in-process broadcast. The only visible degradation is
step-up login, which needs Redis to store the challenge. Everything security- or
correctness-critical works off Postgres.

**Q: What's the role of the `stable_hash` helper?**
A: It's a deterministic SHA-256 of a JSON-serialisable payload with sorted keys, so
logically-identical inputs hash identically. It's used to key the ML prediction cache
off the signal dict and to compute the governance state hash for divergence detection.
Sorting keys is what makes it stable across runs and machines.

**Q: If Redis and the DB disagree on velocity, which wins?**
A: Redis is the fast path and the DB is the fallback — they should agree, but if Redis
is unavailable the code uses the DB count, and if Redis is available it's used directly.
Redis velocity is authoritative when present because it's the live sliding window; the
DB count is a correctness backstop, not a second opinion. They're not reconciled at
read time — it's fallback, not consensus.

---

## "Explain This Decision" (LLM feature)

**Q: You added an LLM to a fraud system. Doesn't that make the model non-deterministic?**
A: No — and this is the key design point. The LLM never touches the decision. The risk
engine computes the score, tier, and action deterministically from ML + rules, *then*
the finished decision plus the structured signals are handed to the LLM, which only
writes a 2–3 sentence explanation of a decision that's already made. It's output-only.
The fraud decision is identical whether or not the LLM ever runs — you can turn the API
key off and the system behaves exactly the same, just with a template explanation
instead of a generated one.

**Q: This is the one feature that costs money per call. How do you keep that bounded?**
A: Five guardrails. It's on-demand only — a button, not something that runs on every
transaction. It's cached in Redis per transaction, so repeat clicks are free. It's
rate-limited more tightly than any other endpoint — 10 per window versus 60 — because
it's the one endpoint that costs real money. It uses the cheapest fast model (Claude
Haiku) with a low max-tokens cap and a hard 5-second timeout with no retries. And if the
key is missing or the call fails, it falls back to a deterministic template. So the cost
is bounded, close to zero, and the feature never blocks or degrades the core pipeline.

**Q: Why the template fallback instead of just erroring?**
A: Two reasons. First, availability — the explanation is a nice-to-have, so a network
blip or missing key should never break the UI or the request. Second, honesty — the
whole project's ethos is being upfront about what's real versus fallback, so every
response carries a `source` field ("llm" or "template") and the UI labels it
"AI-generated" vs "Auto-generated" rather than pretending they're the same. The template
itself is genuinely useful: it names the strongest risk components, so it degrades to
"good enough," not to gibberish.

**Q: How does the explain endpoint get the decision context if the LLM is server-side?**
A: It reconstructs it from what's already stored. When a transaction is analyzed, the
audit log records the risk `components` and top `feature_contributions` in its metadata.
The explain endpoint reads the latest `ANALYZE_*` audit log for that transaction and
passes those to the explainer. So there's no extra state and it's cacheable purely by
transaction id. Access reuses the exact same ownership check as the status endpoint — a
viewer can only explain their own transaction, and I extracted that into one shared
helper rather than writing a second check that could drift.

---

## Governance → model feedback loop

**Q: Walk me through the feedback loop and why it exists.**
A: When the council unanimously approves overturning a fraud decision, that's a
human-verified label — the strongest signal you can get. Before, that signal was thrown
away after updating the transaction and the chain. Now it's captured as training data:
an admin can retrain a candidate model on the synthetic dataset plus those corrections,
weighted higher, and promote it if it's not a regression. It closes the loop between the
governance system and the ML model — real fraud analysts' corrections actually improve
the model.

**Q: Why not just update the model automatically when a correction is approved?**
A: Because a handful of corrections — possibly mislabeled, possibly adversarial if an
admin is compromised — could silently corrupt production with no gate. Online learning
makes the live model a moving target with no reviewable artifact. Instead every retrain
produces a separately versioned candidate file, a regression guard blocks promoting a
candidate whose AUC or recall drops materially versus the live model, and promotion is an
explicit human action. Adaptation is slower, but for fraud scoring, safety and
auditability beat speed. And the unanimous-council requirement is the upstream safety
property — a single admin can't manufacture training data either.

**Q: Why do you snapshot the feature vector instead of recomputing it at retrain time?**
A: This is the subtle correctness point. Several features — velocity, geo-history,
new-device — are time- and state-dependent. If I recomputed them later from current
Redis/DB state, they wouldn't match what the model actually saw when it scored that
transaction. Training on that drifted vector would quietly corrupt the model rather than
improve it. So I persist the exact feature vector at scoring time in a `feature_snapshot`
column, and the loop only uses transactions that have one. I'm explicit that this means
the loop only works for transactions scored after the feature shipped — I don't try to
backfill historical ones by recomputing, precisely because it would be wrong.

**Q: How do you make sure a correction is only used once, and only counts if promotion succeeds?**
A: The proposal has a `consumed_for_training` flag. Corrections are marked consumed only
inside a successful `promote_candidate`, not on every retrain attempt. So if I retrain,
don't like the candidate, and abandon it — or the regression guard blocks it — those
corrections stay available for the next attempt. It makes retraining idempotent and
incremental: a given human correction is folded into exactly one promoted model, ever.

**Q: The retrain can take 30 seconds. How do you handle that in an HTTP API?**
A: It runs as a FastAPI `BackgroundTasks` job, not synchronously in the request — a
30-second admin call would risk timing out on Render's free tier. The retrain endpoint
schedules the job and returns immediately; the frontend polls the summary endpoint, which
exposes a simple `retrain_status` (idle/running/done/error). It's a lightweight version of
an async job queue — appropriate for a single-admin, occasional-retrain workload without
pulling in Celery or a broker.

**Q: How is any of this tested without a 30-second grid search in the suite?**
A: The retrain has a fast path (fixed hyperparameters, no grid search), the same technique
the test-model fixture uses — so tests train a genuine model in a few seconds. The tests
isolate the model path and candidate directory to a temp dir so a promotion test can never
clobber the developer's real model, and they assert the important invariants directly: that
collection only returns approved-unconsumed-with-snapshot corrections, that a retrain writes
a real candidate without touching the live model file, that a deliberately-worse candidate is
blocked without `force` and succeeds with it, and that corrections are consumed only on a
successful promotion.
