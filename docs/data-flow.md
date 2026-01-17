Payment LifeCycle
1. User signs transaction intent
2. Frontend sends request
3. Backend validates input
4. Backend calls AI service
5. AI returns risk score + explanation
6. Backend applies business rules
7. If approved:
   - Blockchain logs immutable record
   - Database stores full details
8. Frontend shows result

Synchronous vs Asynchronous Decisions
-Blocking (Sync)
-Wallet signature verification
-Fraud risk prediction
-Transaction approval / rejection
Non-Blocking (Async)
-Blockchain confirmations
-Event listeners
-Audit logs
-Analytics updates
-This prevents UX freezes and backend bottlenecks.