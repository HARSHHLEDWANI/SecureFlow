/**
 * AuditLog contract tests using raw ethers.js against hardhat's in-process node.
 * Run: npx hardhat compile && npx ts-node --esm test/AuditLog.test.ts
 */
import { ethers } from "ethers";
import { readFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));

let passed = 0;
let failed = 0;

function assert(condition: boolean, msg: string) {
  if (!condition) throw new Error(`Assertion failed: ${msg}`);
}

async function test(name: string, fn: () => Promise<void>) {
  try {
    await fn();
    console.log(`  ✓ ${name}`);
    passed++;
  } catch (err) {
    console.error(`  ✗ ${name}`);
    console.error(`    ${(err as Error).message}`);
    failed++;
  }
}

async function main() {
  console.log("\nAuditLog contract tests\n");

  const provider = new ethers.JsonRpcProvider("http://127.0.0.1:8545");
  const accounts = await provider.listAccounts();
  const owner = await provider.getSigner(0);
  const nonOwner = await provider.getSigner(1);

  const artifactPath = join(__dirname, "../artifacts/contracts/AuditLog.sol/AuditLog.json");
  const artifact = JSON.parse(readFileSync(artifactPath, "utf8"));

  const factory = new ethers.ContractFactory(artifact.abi, artifact.bytecode, owner);
  const contract = await factory.deploy(await owner.getAddress());
  await contract.waitForDeployment();

  const address = await contract.getAddress();
  console.log(`Contract deployed at ${address}\n`);

  await test("stores and retrieves an audit entry correctly", async () => {
    const txId = ethers.keccak256(ethers.toUtf8Bytes("test-tx-001"));
    const fromWallet = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045";
    const toWallet = "0xab5801a7d398351b8be11c439e05c5b3259aec9b";
    const amount = BigInt(50000);
    const riskScore = 35;
    const status = 0;

    const tx = await (contract.connect(owner) as ethers.Contract).logTransaction(
      txId, fromWallet, toWallet, amount, riskScore, status
    );
    await tx.wait();

    const entry = await (contract.connect(owner) as ethers.Contract).getEntry(txId);
    assert(entry.transactionId === txId, "transactionId mismatch");
    assert(entry.fromWallet === fromWallet, "fromWallet mismatch");
    assert(entry.riskScore === BigInt(riskScore), "riskScore mismatch");
    assert(entry.status === BigInt(status), "status mismatch");
  });

  await test("reverts when non-owner calls logTransaction", async () => {
    const txId = ethers.keccak256(ethers.toUtf8Bytes("test-tx-002"));
    let reverted = false;
    try {
      await (contract.connect(nonOwner) as ethers.Contract).logTransaction(
        txId, "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        "0xab5801a7d398351b8be11c439e05c5b3259aec9b", BigInt(100), 10, 0
      );
    } catch {
      reverted = true;
    }
    assert(reverted, "Expected revert for non-owner");
  });

  await test("reverts on duplicate transaction ID", async () => {
    const txId = ethers.keccak256(ethers.toUtf8Bytes("test-tx-003"));
    await (await (contract.connect(owner) as ethers.Contract).logTransaction(
      txId, "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
      "0xab5801a7d398351b8be11c439e05c5b3259aec9b", BigInt(100), 10, 0
    )).wait();

    let reverted = false;
    try {
      await (contract.connect(owner) as ethers.Contract).logTransaction(
        txId, "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        "0xab5801a7d398351b8be11c439e05c5b3259aec9b", BigInt(200), 20, 0
      );
    } catch {
      reverted = true;
    }
    assert(reverted, "Expected revert for duplicate txId");
  });

  await test("reverts getEntry for non-existent transaction", async () => {
    const txId = ethers.keccak256(ethers.toUtf8Bytes("does-not-exist"));
    let reverted = false;
    try {
      await (contract.connect(owner) as ethers.Contract).getEntry(txId);
    } catch {
      reverted = true;
    }
    assert(reverted, "Expected revert for missing entry");
  });

  console.log(`\n${passed} passed, ${failed} failed\n`);
  if (failed > 0) process.exit(1);
}

main().catch((err) => { console.error(err); process.exit(1); });
