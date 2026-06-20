// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title AuditLog
 * @notice Immutable on-chain audit records for SecureFlow transactions.
 *         Only the contract owner (backend deployer wallet) can write records.
 */
contract AuditLog is Ownable {
    enum Status {
        APPROVED,
        FLAGGED,
        REJECTED,
        PENDING
    }

    struct AuditEntry {
        bytes32 transactionId;
        string fromWallet;
        string toWallet;
        uint256 amount;
        uint8 riskScore;
        Status status;
        uint256 timestamp;
        address recorder;
    }

    mapping(bytes32 => AuditEntry) private entries;

    event AuditLogged(
        bytes32 indexed txHash,
        string fromWallet,
        string toWallet,
        uint256 amount,
        uint8 riskScore,
        Status status,
        uint256 timestamp,
        address indexed recorder
    );

    constructor(address initialOwner) Ownable(initialOwner) {}

    /**
     * @notice Log a transaction audit record.
     * @param txId       The SecureFlow transaction UUID (as keccak256 hash).
     * @param fromWallet Source wallet address string.
     * @param toWallet   Destination wallet address string.
     * @param amount     Amount in smallest unit (amount * 100 for 2 decimal precision).
     * @param riskScore  Risk score scaled 0-100 (riskScore * 100 from the float 0-1).
     * @param status     Transaction status enum value.
     * @return auditHash The keccak256 hash of the stored entry (for external verification).
     */
    function logTransaction(
        bytes32 txId,
        string calldata fromWallet,
        string calldata toWallet,
        uint256 amount,
        uint8 riskScore,
        uint8 status
    ) external onlyOwner returns (bytes32 auditHash) {
        require(entries[txId].timestamp == 0, "AuditLog: entry already exists");
        require(riskScore <= 100, "AuditLog: riskScore must be 0-100");
        require(status <= uint8(Status.PENDING), "AuditLog: invalid status");

        AuditEntry memory entry = AuditEntry({
            transactionId: txId,
            fromWallet: fromWallet,
            toWallet: toWallet,
            amount: amount,
            riskScore: riskScore,
            status: Status(status),
            timestamp: block.timestamp,
            recorder: msg.sender
        });

        entries[txId] = entry;

        emit AuditLogged(
            txId,
            fromWallet,
            toWallet,
            amount,
            riskScore,
            Status(status),
            block.timestamp,
            msg.sender
        );

        auditHash = keccak256(abi.encodePacked(txId, block.timestamp, msg.sender));
    }

    /**
     * @notice Retrieve an audit entry by transaction ID hash.
     */
    function getEntry(bytes32 txId) external view returns (AuditEntry memory) {
        require(entries[txId].timestamp != 0, "AuditLog: entry not found");
        return entries[txId];
    }
}
