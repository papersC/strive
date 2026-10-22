const { ethers } = require("hardhat");
const assert = require("assert");
const id = (s) => ethers.keccak256(ethers.toUtf8Bytes(s));
async function reverts(p, msg) {
  try { await p; } catch (e) { const m = (e.shortMessage||e.message); if (msg && !m.includes(msg)) throw new Error(`expected '${msg}' got '${m}'`); return; }
  throw new Error("expected revert");
}
async function setup() {
  const [admin, agent, a1, a2, a3, stu, outsider] = await ethers.getSigners();
  const T = await ethers.deployContract("MockStableToken");
  const V = await ethers.deployContract("SupportFundVault", [await T.getAddress(), admin.address]);
  await V.grantRole(await V.AGENT_ROLE(), agent.address);
  for (const a of [a1,a2,a3]) await V.grantRole(await V.APPROVER_ROLE(), a.address);
  await T.mint(admin.address, 10_000_000n); await T.approve(await V.getAddress(), 10_000_000n); await V.deposit(10_000_000n);
  // programme 1: retention micro-grant 500.00 mAED, auto-approved; programme 2: emergency aid 3000.00, 2-of-3
  await V.createProgramme({minRiskBps:6000,minEngagementBps:5000,approvalsRequired:1,active:true,cooldown:30*24*3600,
     awardAmount:50000n,autoApproveLimit:50000n,perStudentCap:100000n,budget:5_000_000n,committed:0n,rulesHash:id("retention-v1")});
  await V.createProgramme({minRiskBps:7000,minEngagementBps:0,approvalsRequired:2,active:true,cooldown:0,
     awardAmount:300000n,autoApproveLimit:0n,perStudentCap:300000n,budget:600000n,committed:0n,rulesHash:id("emergency-v1")});
  const pid = id("salt|student-001");
  await V.registerStudent(pid, stu.address);
  return { admin, agent, a1, a2, a3, stu, outsider, T, V, pid };
}
describe("SupportFundVault security properties", function () {
  it("S1 only the agent role can request awards", async () => {
    const { V, outsider, pid } = await setup();
    await reverts(V.connect(outsider).requestAward(1, pid, 9000, 9000, id("e")), "AccessControlUnauthorizedAccount");
  });
  it("S2 on-chain rule enforcement: risk and engagement thresholds", async () => {
    const { V, agent, pid } = await setup();
    await reverts(V.connect(agent).requestAward(1, pid, 5999, 9000, id("e")), "NotEligible");
    await reverts(V.connect(agent).requestAward(1, pid, 9000, 4999, id("e")), "NotEligible");
  });
  it("S3 unregistered pseudonym rejected", async () => {
    const { V, agent } = await setup();
    await reverts(V.connect(agent).requestAward(1, id("ghost"), 9000, 9000, id("e")), "NotEligible");
  });
  it("S4 auto-approved award disbursed to registered wallet with event trail", async () => {
    const { V, T, agent, stu, pid } = await setup();
    const tx = await V.connect(agent).requestAward(1, pid, 8200, 7000, id("evidence"));
    const rc = await tx.wait();
    const names = rc.logs.map(l => { try { return V.interface.parseLog(l).name } catch { return null } }).filter(Boolean);
    assert.deepStrictEqual(names, ["AwardRequested","AwardDisbursed"]);
    assert.strictEqual(await T.balanceOf(stu.address), 50000n);
  });
  it("S5 cooldown prevents duplicate/rapid awards", async () => {
    const { V, agent, pid } = await setup();
    await V.connect(agent).requestAward(1, pid, 8200, 7000, id("e1"));
    await reverts(V.connect(agent).requestAward(1, pid, 8200, 7000, id("e2")), "NotEligible");
  });
  it("S6 per-student cap enforced across cooldown windows", async () => {
    const { V, agent, pid } = await setup();
    for (let i = 0; i < 2; i++) { await V.connect(agent).requestAward(1, pid, 8200, 7000, id("e"+i)); await ethers.provider.send("evm_increaseTime",[31*24*3600]); await ethers.provider.send("evm_mine",[]); }
    await reverts(V.connect(agent).requestAward(1, pid, 8200, 7000, id("e3")), "NotEligible");
  });
  it("S7 M-of-N approval: large award pending until 2 distinct approvers", async () => {
    const { V, T, agent, a1, a2, stu, pid } = await setup();
    await V.connect(agent).requestAward(2, pid, 9100, 0, id("hardship"));
    assert.strictEqual(await T.balanceOf(stu.address), 0n);
    await V.connect(a1).approve(0);
    await reverts(V.connect(a1).approve(0), "already approved");
    assert.strictEqual(await T.balanceOf(stu.address), 0n);
    await V.connect(a2).approve(0);
    assert.strictEqual(await T.balanceOf(stu.address), 300000n);
    await reverts(V.connect(a2).approve(0), "not pending");
  });
  it("S8 programme budget cannot be exceeded", async () => {
    const { V, agent, admin } = await setup();
    for (let i = 0; i < 3; i++) { const p = id("s"+i); await V.connect(admin).registerStudent(p, admin.address);
      if (i < 2) await V.connect(agent).requestAward(2, p, 9100, 0, id("h"+i));
      else await reverts(V.connect(agent).requestAward(2, p, 9100, 0, id("h"+i)), "NotEligible"); }
  });
  it("S9 rejection releases reserved budget", async () => {
    const { V, agent, a1, pid } = await setup();
    await V.connect(agent).requestAward(2, pid, 9100, 0, id("h"));
    await V.connect(a1).reject(0, id("insufficient documentation"));
    const p = await V.programmes(2); assert.strictEqual(p.committed, 0n);
  });
  it("S10 emergency pause halts agent requests", async () => {
    const { V, agent, admin, pid } = await setup();
    await V.connect(admin).pause();
    await reverts(V.connect(agent).requestAward(1, pid, 9000, 9000, id("e")), "EnforcedPause");
  });
  it("S11 only the student's wallet can file an appeal", async () => {
    const { V, stu, outsider, pid } = await setup();
    await reverts(V.connect(outsider).fileAppeal(pid, 0, id("r")), "not student");
    await (await V.connect(stu).fileAppeal(pid, 0, id("r"))).wait();
  });
  it("S12 re-entrancy during token transfer is blocked", async () => {
    const [admin, agent, stu] = await ethers.getSigners();
    const E = await ethers.deployContract("ReentrantToken");
    const V = await ethers.deployContract("SupportFundVault", [await E.getAddress(), admin.address]);
    await V.grantRole(await V.AGENT_ROLE(), agent.address);
    await V.grantRole(await V.AGENT_ROLE(), await E.getAddress());
    await E.mint(await V.getAddress(), 10_000_000n);
    await V.createProgramme({minRiskBps:0,minEngagementBps:0,approvalsRequired:1,active:true,cooldown:0,
      awardAmount:1000n,autoApproveLimit:1000n,perStudentCap:100000n,budget:1_000_000n,committed:0n,rulesHash:id("x")});
    const p = id("victim"); await V.registerStudent(p, stu.address);
    await E.arm(await V.getAddress(), p);
    await reverts(V.connect(agent).requestAward(1, p, 9000, 9000, id("e")), "ReentrancyGuardReentrantCall");
    assert.strictEqual(await V.totalRequests(), 0n);
  });
  it("S13 policy admin cannot shrink budget below committed funds", async () => {
    const { V, agent, admin, pid } = await setup();
    await V.connect(agent).requestAward(1, pid, 9000, 9000, id("e"));
    await reverts(V.connect(admin).setProgrammeStatus(1, true, 10000n), "budget below committed");
  });
});
describe("InterventionRegistry security properties", function () {
  async function reg() { const [admin, agent, adv, outsider] = await ethers.getSigners();
    const R = await ethers.deployContract("InterventionRegistry", [admin.address]);
    await R.grantRole(await R.AGENT_ROLE(), agent.address); await R.grantRole(await R.ADVISOR_ROLE(), adv.address);
    return { R, admin, agent, adv, outsider }; }
  it("R1 only the agent can log interventions and anchor snapshots", async () => {
    const { R, outsider } = await reg();
    await reverts(R.connect(outsider).logIntervention(id("p"), 0, 8000, id("plan"), id("m")), "AccessControlUnauthorizedAccount");
    await reverts(R.connect(outsider).anchorRiskSnapshot(id("root"), id("m"), 10), "AccessControlUnauthorizedAccount");
  });
  it("R2 agent cannot close interventions; only advisors record outcomes", async () => {
    const { R, agent, adv } = await reg();
    await R.connect(agent).logIntervention(id("p"), 1, 8000, id("plan"), id("m"));
    await reverts(R.connect(agent).updateStatus(0, 3, id("o")), "not authorised");
    await R.connect(agent).updateStatus(0, 5, id("escalate"));
    await R.connect(adv).updateStatus(0, 3, id("done"));
    await reverts(R.connect(adv).updateStatus(0, 2, id("reopen")), "closed");
  });
  it("R3 malformed risk scores rejected", async () => {
    const { R, agent } = await reg();
    await reverts(R.connect(agent).logIntervention(id("p"), 1, 10001, id("plan"), id("m")), "risk out of range");
  });
});
