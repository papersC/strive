// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

/// @title STRIVE SupportFundVault
/// @notice Rule-based, auditable disbursement of scholarships, retention incentives and emergency aid.
///         Eligibility rules are encoded per programme; the AI agent can only *request* awards, and
///         every request is checked on-chain against the published rules. Awards above a threshold
///         require M-of-N human approvals (human-in-the-loop). All state changes emit events.
contract SupportFundVault is AccessControl, Pausable, ReentrancyGuard {
    using SafeERC20 for IERC20;
    bytes32 public constant POLICY_ADMIN_ROLE = keccak256("POLICY_ADMIN_ROLE"); // financial-aid office
    bytes32 public constant AGENT_ROLE        = keccak256("AGENT_ROLE");        // agent oracle account
    bytes32 public constant APPROVER_ROLE     = keccak256("APPROVER_ROLE");     // aid committee members

    IERC20 public immutable token;

    struct Programme {
        uint16  minRiskBps;          // minimum risk score to qualify (needs-based early-warning aid)
        uint16  minEngagementBps;    // minimum engagement with the planned intervention (conditional incentive)
        uint8   approvalsRequired;   // M in M-of-N for awards above autoApproveLimit
        bool    active;
        uint32  cooldown;            // minimum seconds between two awards to the same student
        uint128 awardAmount;         // fixed award per request (token base units)
        uint128 autoApproveLimit;    // awards <= limit are released immediately
        uint128 perStudentCap;       // lifetime cap per student within the programme
        uint128 budget;              // total budget allocated to the programme
        uint128 committed;           // disbursed + pending
        bytes32 rulesHash;           // hash of the human-readable policy document
    }
    struct Student { address wallet; bool registered; }
    enum ReqState { None, Pending, Disbursed, Rejected }
    struct Request {
        uint32  programmeId; ReqState state; uint8 approvals; uint64 createdAt;
        uint128 amount; bytes32 pseudoId; bytes32 evidenceHash;
    }

    mapping(uint32 => Programme) public programmes;
    uint32 public programmeCount;
    mapping(bytes32 => Student) public students;
    mapping(uint32 => mapping(bytes32 => uint128)) public receivedBy;   // programme => student => total
    mapping(uint32 => mapping(bytes32 => uint64))  public lastAwardAt;
    Request[] public requests;
    mapping(uint256 => mapping(address => bool)) public approvedBy;

    event ProgrammeCreated(uint32 indexed id, bytes32 rulesHash, uint128 budget);
    event ProgrammeUpdated(uint32 indexed id, bool active, uint128 budget);
    event StudentRegistered(bytes32 indexed pseudoId, address wallet);
    event FundsDeposited(address indexed from, uint256 amount);
    event AwardRequested(uint256 indexed requestId, uint32 indexed programmeId, bytes32 indexed pseudoId,
                         uint128 amount, uint16 riskBps, uint16 engagementBps, bytes32 evidenceHash, bool autoApproved);
    event AwardApproved(uint256 indexed requestId, address indexed approver, uint8 approvals);
    event AwardDisbursed(uint256 indexed requestId, bytes32 indexed pseudoId, address wallet, uint128 amount);
    event AwardRejected(uint256 indexed requestId, address indexed by, bytes32 reasonHash);
    event AppealFiled(bytes32 indexed pseudoId, uint256 indexed requestId, bytes32 reasonHash);

    error NotEligible(string reason);

    constructor(IERC20 token_, address admin) {
        token = token_;
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(POLICY_ADMIN_ROLE, admin);
    }

    // ------------------------------------------------------------------ administration
    function createProgramme(Programme calldata p) external onlyRole(POLICY_ADMIN_ROLE) returns (uint32 id) {
        require(p.awardAmount > 0 && p.perStudentCap >= p.awardAmount, "bad amounts");
        require(p.approvalsRequired > 0 && p.minRiskBps <= 10000 && p.minEngagementBps <= 10000, "bad params");
        id = ++programmeCount;
        Programme storage s = programmes[id];
        s.minRiskBps = p.minRiskBps; s.minEngagementBps = p.minEngagementBps; s.approvalsRequired = p.approvalsRequired;
        s.active = true; s.cooldown = p.cooldown; s.awardAmount = p.awardAmount; s.autoApproveLimit = p.autoApproveLimit;
        s.perStudentCap = p.perStudentCap; s.budget = p.budget; s.rulesHash = p.rulesHash;
        emit ProgrammeCreated(id, p.rulesHash, p.budget);
    }
    function setProgrammeStatus(uint32 id, bool active, uint128 budget) external onlyRole(POLICY_ADMIN_ROLE) {
        Programme storage s = programmes[id];
        require(budget >= s.committed, "budget below committed");
        s.active = active; s.budget = budget;
        emit ProgrammeUpdated(id, active, budget);
    }
    function registerStudent(bytes32 pseudoId, address wallet) external onlyRole(POLICY_ADMIN_ROLE) {
        require(wallet != address(0), "zero wallet");
        students[pseudoId] = Student(wallet, true);
        emit StudentRegistered(pseudoId, wallet);
    }
    function deposit(uint256 amount) external {
        token.safeTransferFrom(msg.sender, address(this), amount);
        emit FundsDeposited(msg.sender, amount);
    }

    // ------------------------------------------------------------------ agent entry point
    /// @notice Called by the agent oracle. Rules are re-checked on-chain; the agent cannot bypass them.
    function requestAward(uint32 programmeId, bytes32 pseudoId, uint16 riskBps, uint16 engagementBps, bytes32 evidenceHash)
        external onlyRole(AGENT_ROLE) whenNotPaused nonReentrant returns (uint256 requestId)
    {
        Programme storage p = programmes[programmeId];
        if (!p.active) revert NotEligible("programme inactive");
        if (!students[pseudoId].registered) revert NotEligible("unregistered");
        if (riskBps < p.minRiskBps || riskBps > 10000) revert NotEligible("risk rule");
        if (engagementBps < p.minEngagementBps) revert NotEligible("engagement rule");
        uint64 last = lastAwardAt[programmeId][pseudoId];
        if (last != 0 && block.timestamp < last + p.cooldown) revert NotEligible("cooldown");
        uint128 amt = p.awardAmount;
        if (receivedBy[programmeId][pseudoId] + amt > p.perStudentCap) revert NotEligible("student cap");
        if (p.committed + amt > p.budget) revert NotEligible("budget");

        p.committed += amt;
        receivedBy[programmeId][pseudoId] += amt;     // reserved immediately to prevent double requests
        lastAwardAt[programmeId][pseudoId] = uint64(block.timestamp);
        requestId = requests.length;
        bool auto_ = amt <= p.autoApproveLimit;
        requests.push(Request(programmeId, ReqState.Pending, 0, uint64(block.timestamp), amt, pseudoId, evidenceHash));
        emit AwardRequested(requestId, programmeId, pseudoId, amt, riskBps, engagementBps, evidenceHash, auto_);
        if (auto_) _disburse(requestId);
    }

    // ------------------------------------------------------------------ human-in-the-loop
    function approve(uint256 requestId) external onlyRole(APPROVER_ROLE) whenNotPaused nonReentrant {
        Request storage r = requests[requestId];
        require(r.state == ReqState.Pending, "not pending");
        require(!approvedBy[requestId][msg.sender], "already approved");
        approvedBy[requestId][msg.sender] = true;
        r.approvals += 1;
        emit AwardApproved(requestId, msg.sender, r.approvals);
        if (r.approvals >= programmes[r.programmeId].approvalsRequired) _disburse(requestId);
    }
    function reject(uint256 requestId, bytes32 reasonHash) external onlyRole(APPROVER_ROLE) nonReentrant {
        Request storage r = requests[requestId];
        require(r.state == ReqState.Pending, "not pending");
        r.state = ReqState.Rejected;
        programmes[r.programmeId].committed -= r.amount;
        receivedBy[r.programmeId][r.pseudoId] -= r.amount;
        emit AwardRejected(requestId, msg.sender, reasonHash);
    }
    /// @notice Contestability: the student's registered wallet can file an appeal referencing an off-chain statement.
    function fileAppeal(bytes32 pseudoId, uint256 requestId, bytes32 reasonHash) external {
        require(students[pseudoId].registered && students[pseudoId].wallet == msg.sender, "not student");
        emit AppealFiled(pseudoId, requestId, reasonHash);
    }

    function _disburse(uint256 requestId) internal {
        Request storage r = requests[requestId];
        r.state = ReqState.Disbursed;                       // effects before interaction
        address w = students[r.pseudoId].wallet;
        token.safeTransfer(w, r.amount);
        emit AwardDisbursed(requestId, r.pseudoId, w, r.amount);
    }

    function totalRequests() external view returns (uint256) { return requests.length; }
    function pause() external onlyRole(DEFAULT_ADMIN_ROLE) { _pause(); }
    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) { _unpause(); }
}
