Trust Boundaries

| Layer      | Trust Level    | Reason          |
| ---------- | -------------- | --------------- |
| Frontend   | ❌ Untrusted    | User controlled |
| AI Service | ⚠ Advisory     | Probabilistic   |
| Backend    | ⚠ Semi-trusted | Enforces logic  |
| Database   | ⚠ Controlled   | Mutable         |
| Blockchain | ✅ Trusted      | Immutable       |


## Why the Backend Is the Authority

The backend is the system’s authority because it is the only component that is trusted, deterministic, and capable of enforcing decisions.

- **Frontend is untrusted**  
  Runs on the user’s device and can be modified or bypassed. It cannot enforce rules or guarantee integrity.

- **AI is probabilistic**  
  Produces risk scores and predictions, not facts. It can be wrong and must remain advisory.

- **Blockchain is immutable but rigid**  
  Ideal for audit and proof, but inefficient for complex logic, updates, or real-time decision-making.

- **Backend has full system context**  
  It is the only layer that has access to user authentication, business rules, AI risk output, database state, and blockchain interactions.

- **Backend decisions are enforceable**  
  It can approve, reject, delay, or rollback workflows and apply fallback logic when dependencies fail.

**Conclusion:**  
The backend acts as the single decision authority that safely orchestrates AI recommendations and blockchain proofs while enforcing business rules.
