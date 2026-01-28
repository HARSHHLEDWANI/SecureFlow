export type RiskLevel = 'low' | 'medium' | 'high';
export type AuditStatus = 'verified' | 'pending' | 'failed';
export type Transaction = {
  id: string;
  fromWallet: string;
  toWallet: string;
  amount: number;
  currency: string;
  timestamp: string;

  status: "APPROVED" | "FLAGGED" | "REJECTED" | "PENDING";

  riskScore?: number;
  riskLevel: RiskLevel;

  // 🔗 Blockchain audit proof
  auditTxHash?: string;
  auditedAt?: string;
  sender: string;
  receiver: string;
  auditStatus: AuditStatus;
  aiExplanation: string;
  modelVersion: string;
  createdAt: string;
};
