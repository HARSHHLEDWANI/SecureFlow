export function AuditBadge({ audited }: { audited: boolean }) {
  if (!audited) {
    return (
      <span className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-600">
        ⏳ Pending audit
      </span>
    );
  }

  return (
    <span className="text-xs px-2 py-1 rounded bg-blue-100 text-blue-800">
      🔒 Audited on-chain
    </span>
  );
}
