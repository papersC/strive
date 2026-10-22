// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";

/// @title STRIVE InterventionRegistry
/// @notice Tamper-evident log of agent-planned interventions and of hashed risk-score snapshots.
///         No personal data is stored: students are referenced by salted pseudonymous identifiers and
///         plans/outcomes by content hashes of off-chain records.
contract InterventionRegistry is AccessControl, Pausable {
    bytes32 public constant AGENT_ROLE   = keccak256("AGENT_ROLE");
    bytes32 public constant ADVISOR_ROLE = keccak256("ADVISOR_ROLE");

    enum Kind   { AdvisorAlert, TutoringReferral, WellbeingReferral, FinancialCounselling, PeerMentoring }
    enum Status { Planned, Acknowledged, InProgress, Completed, Declined, Escalated }

    struct Intervention {
        bytes32 pseudoId;      // salted hash of student identifier
        bytes32 planHash;      // hash of the off-chain intervention plan (agent rationale, evidence)
        bytes32 outcomeHash;   // hash of the off-chain outcome note
        bytes32 modelVersion;  // identifies the risk model / agent policy version used
        uint16  riskBps;       // risk score in basis points (0-10000)
        Kind    kind;
        Status  status;
        uint64  createdAt;
        uint64  updatedAt;
    }
    struct Snapshot { bytes32 merkleRoot; bytes32 modelVersion; uint32 count; uint64 timestamp; }

    Intervention[] private _items;
    Snapshot[] public snapshots;

    event InterventionLogged(uint256 indexed id, bytes32 indexed pseudoId, Kind kind, uint16 riskBps, bytes32 planHash, bytes32 modelVersion);
    event InterventionStatus(uint256 indexed id, Status status, bytes32 outcomeHash, address indexed by);
    event RiskSnapshotAnchored(uint256 indexed id, bytes32 merkleRoot, bytes32 modelVersion, uint32 count);

    constructor(address admin) { _grantRole(DEFAULT_ADMIN_ROLE, admin); }

    function logIntervention(bytes32 pseudoId, Kind kind, uint16 riskBps, bytes32 planHash, bytes32 modelVersion)
        external onlyRole(AGENT_ROLE) whenNotPaused returns (uint256 id)
    {
        id = _log(pseudoId, kind, riskBps, planHash, modelVersion);
    }

    function logBatch(bytes32[] calldata pseudoIds, Kind[] calldata kinds, uint16[] calldata risks,
                      bytes32[] calldata planHashes, bytes32 modelVersion)
        external onlyRole(AGENT_ROLE) whenNotPaused returns (uint256 firstId)
    {
        uint256 n = pseudoIds.length;
        require(n > 0 && kinds.length == n && risks.length == n && planHashes.length == n, "length mismatch");
        firstId = _items.length;
        for (uint256 i; i < n; ++i) _log(pseudoIds[i], kinds[i], risks[i], planHashes[i], modelVersion);
    }

    function _log(bytes32 pseudoId, Kind kind, uint16 riskBps, bytes32 planHash, bytes32 modelVersion) internal returns (uint256 id) {
        require(riskBps <= 10000, "risk out of range");
        id = _items.length;
        _items.push(Intervention(pseudoId, planHash, bytes32(0), modelVersion, riskBps, kind, Status.Planned,
                                 uint64(block.timestamp), uint64(block.timestamp)));
        emit InterventionLogged(id, pseudoId, kind, riskBps, planHash, modelVersion);
    }

    /// @notice Human advisors (or the agent, for escalation) record status transitions.
    function updateStatus(uint256 id, Status status, bytes32 outcomeHash) external whenNotPaused {
        require(hasRole(ADVISOR_ROLE, msg.sender) || (hasRole(AGENT_ROLE, msg.sender) && status == Status.Escalated), "not authorised");
        Intervention storage it = _items[id];
        require(it.status != Status.Completed && it.status != Status.Declined, "closed");
        require(status != Status.Planned, "invalid transition");
        it.status = status; it.outcomeHash = outcomeHash; it.updatedAt = uint64(block.timestamp);
        emit InterventionStatus(id, status, outcomeHash, msg.sender);
    }

    function anchorRiskSnapshot(bytes32 merkleRoot, bytes32 modelVersion, uint32 count)
        external onlyRole(AGENT_ROLE) whenNotPaused returns (uint256 id)
    {
        id = snapshots.length;
        snapshots.push(Snapshot(merkleRoot, modelVersion, count, uint64(block.timestamp)));
        emit RiskSnapshotAnchored(id, merkleRoot, modelVersion, count);
    }

    function getIntervention(uint256 id) external view returns (Intervention memory) { return _items[id]; }
    function totalInterventions() external view returns (uint256) { return _items.length; }
    function pause() external onlyRole(DEFAULT_ADMIN_ROLE) { _pause(); }
    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) { _unpause(); }
}
