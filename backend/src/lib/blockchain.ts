import { ethers } from "ethers";
import AuditLogArtifact from "../../../blockchain/artifacts/contracts/AuditLog.sol/AuditLog.json";

const RPC_URL = "http://127.0.0.1:8545";
const CONTRACT_ADDRESS = "0x73511669fd4dE447feD18BB79bAFeAC93aB7F31f";
const PRIVATE_KEY = "0xdf57089febbacf7ba0bc227dafbffa9fc08a93fdc68e1e42411a14efcf23656e";

const provider = new ethers.JsonRpcProvider(RPC_URL);
const wallet = new ethers.Wallet(PRIVATE_KEY, provider);

export const auditLogContract = new ethers.Contract(
  CONTRACT_ADDRESS,
  AuditLogArtifact.abi,
  wallet
);

export const logAuditOnChain = async (params: {
  transactionId: string;
  decision: "APPROVED" | "FLAGGED" | "REJECTED";
  riskScore: number | null;
}) => {
  const decisionMap = {
    APPROVED: 0,
    FLAGGED: 1,
    REJECTED: 2,
  };

  const tx = await auditLogContract.logAudit(
    ethers.id(params.transactionId),
    decisionMap[params.decision],
    params.riskScore !== null
      ? Math.floor(params.riskScore * 10_000)
      : 0
  );

  const receipt = await tx.wait();
  console.log("Audit tx hash:", receipt.hash);
  return {
  txHash: receipt.hash,
};

};
