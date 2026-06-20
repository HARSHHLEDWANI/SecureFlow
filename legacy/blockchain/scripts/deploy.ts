/**
 * Deploy AuditLog contract using raw ethers.js.
 * Run after `npx hardhat compile`:
 *   npx ts-node --esm scripts/deploy.ts           (localhost)
 *   HARDHAT_NETWORK=sepolia npx ts-node --esm scripts/deploy.ts
 */
import { ethers } from "ethers";
import { readFileSync, mkdirSync, writeFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import * as dotenv from "dotenv";

const __dirname = dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: join(__dirname, "../../backend/.env") });

const HARDHAT_DEFAULT_KEY = "0xdf57089febbacf7ba0bc227dafbffa9fc08a93fdc68e1e42411a14efcf23656e";

async function main() {
  const network = process.env.HARDHAT_NETWORK ?? "localhost";
  const rpcUrl =
    network === "sepolia"
      ? process.env.SEPOLIA_RPC_URL!
      : "http://127.0.0.1:8545";
  const privateKey =
    network === "sepolia"
      ? process.env.DEPLOYER_PRIVATE_KEY!
      : HARDHAT_DEFAULT_KEY;

  if (!rpcUrl) throw new Error("SEPOLIA_RPC_URL is not set");
  if (!privateKey) throw new Error("DEPLOYER_PRIVATE_KEY is not set");

  const provider = new ethers.JsonRpcProvider(rpcUrl);
  const wallet = new ethers.Wallet(privateKey, provider);
  console.log("Deploying with account:", wallet.address);

  const artifactPath = join(__dirname, "../artifacts/contracts/AuditLog.sol/AuditLog.json");
  const artifact = JSON.parse(readFileSync(artifactPath, "utf8"));

  const factory = new ethers.ContractFactory(artifact.abi, artifact.bytecode, wallet);
  const contract = await factory.deploy(wallet.address);
  await contract.waitForDeployment();

  const address = await contract.getAddress();
  console.log("AuditLog deployed to:", address);

  const deploymentsDir = join(__dirname, "../deployments");
  mkdirSync(deploymentsDir, { recursive: true });
  writeFileSync(
    join(deploymentsDir, `${network}.json`),
    JSON.stringify({ address, deployer: wallet.address, deployedAt: new Date().toISOString() }, null, 2)
  );
  console.log(`Saved to deployments/${network}.json`);
}

main().catch((err) => { console.error(err); process.exit(1); });
