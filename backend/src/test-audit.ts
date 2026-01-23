import { logAuditOnChain } from "./lib/blockchain";

async function test() {
  const res = await logAuditOnChain({
    transactionId: "test-123",
    decision: "APPROVED",
    riskScore: 0.42,
  });

  console.log("Returned audit tx hash:", res.txHash);
}

test();
