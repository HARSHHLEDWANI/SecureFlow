-- AlterTable
ALTER TABLE "Transaction" ADD COLUMN     "auditTxHash" TEXT,
ADD COLUMN     "auditedAt" TIMESTAMP(3);
