// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

contract AuditLog {
    enum Decision {
        APPROVED,
        FLAGGED,
        REJECTED
    }

    struct AuditEntry {
        bytes32 transactionId;
        Decision decision;
        uint256 riskScore;
        uint256 timestamp;
        address recordedBy;
    }

    address public backendSigner;

    mapping(bytes32 => AuditEntry) private auditLogs;

    event AuditLogged(
        bytes32 indexed transactionId,
        Decision decision,
        uint256 riskScore,
        uint256 timestamp,
        address indexed recordedBy
    );

    modifier onlyBackend() {
        require(msg.sender == backendSigner, "Not authorized");
        _;
    }

    constructor(address _backendSigner) {
        backendSigner = _backendSigner;
    }

    function logAudit(
        bytes32 transactionId,
        Decision decision,
        uint256 riskScore
    ) external onlyBackend {
        require(
            auditLogs[transactionId].timestamp == 0,
            "Audit already exists"
        );

        auditLogs[transactionId] = AuditEntry({
            transactionId: transactionId,
            decision: decision,
            riskScore: riskScore,
            timestamp: block.timestamp,
            recordedBy: msg.sender
        });

        emit AuditLogged(
            transactionId,
            decision,
            riskScore,
            block.timestamp,
            msg.sender
        );
    }

    function getAudit(bytes32 transactionId)
        external
        view
        returns (AuditEntry memory)
    {
        require(
            auditLogs[transactionId].timestamp != 0,
            "Audit not found"
        );

        return auditLogs[transactionId];
    }
}
