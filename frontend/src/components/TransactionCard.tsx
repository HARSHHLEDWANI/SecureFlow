
import { Transaction } from "@/types/transaction";
import { AuditBadge } from "./AuditBadge";
import { StatusExplanation } from "./StatusExplanation";

function statusColor(status: Transaction["status"]) {
  switch (status) {
    case "APPROVED":
      return "bg-green-100 text-green-800";
    case "FLAGGED":
      return "bg-yellow-100 text-yellow-800";
    case "REJECTED":
      return "bg-red-100 text-red-800";
    default:
      return "bg-gray-100 text-gray-800";
  }
}

export function TransactionCard({ tx }: { tx: Transaction }) {
  return (
    <div className="border rounded-lg p-4 space-y-2">
      <div className="flex justify-between items-center">
        <span className="text-sm text-gray-500">
          {new Date(tx.createdAt).toLocaleString()}
        </span>

        <span
          className={`text-xs font-medium px-2 py-1 rounded ${statusColor(
            tx.status
          )}`}
        >
          {tx.status}
        </span>

        <AuditBadge audited={Boolean(tx.auditTxHash)} />
        <StatusExplanation status={tx.status} />
      </div>

      <div className="text-sm">
        <div>
          <strong>From:</strong> {tx.fromWallet}
        </div>
        <div>
          <strong>To:</strong> {tx.toWallet}
        </div>
      </div>

      <div className="flex justify-between items-center text-sm">
        <span>
          <strong>Amount:</strong> {tx.amount} {tx.currency}
        </span>

        <span>
          <strong>Risk:</strong>{" "}
          {typeof tx.riskScore === "number" ? tx.riskScore.toFixed(2) : "N/A"}


        </span>
      </div>
    </div>
  );
}
