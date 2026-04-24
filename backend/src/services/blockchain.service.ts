import { ethers } from "ethers";
import { logger } from "../lib/logger";

const AUDIT_LOG_ABI = [
  "function logTransaction(bytes32 txId, string fromWallet, string toWallet, uint256 amount, uint8 riskScore, uint8 status) external returns (bytes32)",
  "function getEntry(bytes32 txId) external view returns (tuple(bytes32 transactionId, string fromWallet, string toWallet, uint256 amount, uint8 riskScore, uint8 status, uint256 timestamp, address recorder))",
];

function getContract(): ethers.Contract | null {
  const rpcUrl = process.env.SEPOLIA_RPC_URL;
  const contractAddress = process.env.CONTRACT_ADDRESS;
  const privateKey = process.env.DEPLOYER_PRIVATE_KEY;

  if (!rpcUrl || !contractAddress || !privateKey) return null;

  try {
    const provider = new ethers.JsonRpcProvider(rpcUrl);
    const wallet = new ethers.Wallet(privateKey, provider);
    return new ethers.Contract(contractAddress, AUDIT_LOG_ABI, wallet);
  } catch {
    return null;
  }
}

export async function logToBlockchain(
  txId: string,
  fromWallet: string,
  toWallet: string,
  amount: number,
  riskScore: number,
  status: string
): Promise<string | null> {
  try {
    const contract = getContract();
    if (!contract) {
      logger.warn("Blockchain service not configured — skipping on-chain log");
      return null;
    }

    const txIdBytes = ethers.keccak256(ethers.toUtf8Bytes(txId));
    const amountWei = BigInt(Math.round(amount * 100));
    const riskScoreInt = Math.round(riskScore * 100);
    const statusInt = ["APPROVED", "FLAGGED", "REJECTED", "PENDING"].indexOf(status);

    const tx = await contract.logTransaction(
      txIdBytes,
      fromWallet,
      toWallet,
      amountWei,
      riskScoreInt,
      statusInt >= 0 ? statusInt : 0
    );
    const receipt = await tx.wait();
    return receipt.hash as string;
  } catch (err) {
    logger.error({ err }, "Blockchain logging failed — continuing without on-chain record");
    return null;
  }
}
