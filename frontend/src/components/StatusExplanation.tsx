import { Transaction } from "@/types/transaction";

export function StatusExplanation({
  status,
}: {
  status: Transaction["status"];
}) {
  switch (status) {
    case "APPROVED":
      return (
        <p className="text-xs text-green-700">
          Transaction approved by backend after risk evaluation.
        </p>
      );

    case "FLAGGED":
      return (
        <p className="text-xs text-yellow-700">
          Transaction flagged due to elevated risk. Manual review required.
        </p>
      );

    case "REJECTED":
      return (
        <p className="text-xs text-red-700">
          Transaction rejected due to high fraud risk.
        </p>
      );

    default:
      return (
        <p className="text-xs text-gray-600">
          Transaction pending evaluation.
        </p>
      );
  }
}
