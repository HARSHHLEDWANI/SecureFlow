import React from 'react';

interface AuditBadgeProps {
  status: 'verified' | 'pending' | 'failed';
}

export const AuditBadge = ({ status }: AuditBadgeProps) => {
  const styles = {
    verified: "bg-emerald-50 text-emerald-700 border-emerald-200",
    pending: "bg-amber-50 text-amber-700 border-amber-200",
    failed: "bg-red-50 text-red-700 border-red-200",
  };

  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${styles[status]}`}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
};