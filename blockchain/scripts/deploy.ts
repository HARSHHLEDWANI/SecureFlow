import { ethers } from "ethers";
import fs from "fs";
import path from "path";

async function main() {
  // Connect to local Hardhat node
  const provider = new ethers.JsonRpcProvider("http://127.0.0.1:8545");

  // Use first Hardhat account private key
  const privateKey =
    "";
  const wallet = new ethers.Wallet(privateKey, provider);

  console.log("Deploying with account:", wallet.address);

  // Load compiled artifact
  const artifactPath = path.join(
    process.cwd(),
    "artifacts/contracts/AuditLog.sol/AuditLog.json"
  );
  const artifact = JSON.parse(fs.readFileSync(artifactPath, "utf8"));

  const factory = new ethers.ContractFactory(
    artifact.abi,
    artifact.bytecode,
    wallet
  );

  const contract = await factory.deploy(wallet.address);
  await contract.waitForDeployment();

  console.log("AuditLog deployed to:", await contract.getAddress());
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
