// On-chain benchmark for STRIVE contracts. Run against a local Hardhat JSON-RPC node.
// usage: BLOCKTIME=0|2000 npx hardhat run scripts/bench.js --network localhost
const { ethers, network } = require("hardhat");
const fs = require("fs");
const id = (s) => ethers.keccak256(ethers.toUtf8Bytes(s));
const OUT = "/workspace/papers/paper5/results/";
const BT = parseInt(process.env.BLOCKTIME || "0");
async function timed(fn) { const t = process.hrtime.bigint(); const tx = await fn(); const rc = await tx.wait(); return { gas: rc.gasUsed, ms: Number(process.hrtime.bigint() - t) / 1e6, rc }; }
const stats = (a) => { const s=[...a].sort((x,y)=>x-y); const m=a.reduce((x,y)=>x+y,0)/a.length; const sd=Math.sqrt(a.reduce((x,y)=>x+(y-m)**2,0)/a.length);
  return { n:a.length, mean:m, sd, p50:s[Math.floor(.5*(s.length-1))], p95:s[Math.floor(.95*(s.length-1))], min:s[0], max:s[s.length-1] }; };
async function main() {
  if (BT > 0) { await network.provider.send("evm_setAutomine", [false]); await network.provider.send("evm_setIntervalMining", [BT]); }
  else { await network.provider.send("evm_setIntervalMining", [0]); await network.provider.send("evm_setAutomine", [true]); }
  const [admin, agent, a1, a2, a3, ...rest] = await ethers.getSigners();
  const res = { blocktime_ms: BT, deploy: {}, ops: {}, latency: {}, batch: {}, scenario: {} };
  const dep = async (name, args) => { const f = await ethers.getContractFactory(name); const c = await f.deploy(...args); const rc = await c.deploymentTransaction().wait(); res.deploy[name] = Number(rc.gasUsed); return c; };
  const T = await dep("MockStableToken", []);
  const V = await dep("SupportFundVault", [await T.getAddress(), admin.address]);
  const R = await dep("InterventionRegistry", [admin.address]);
  for (const c of [V, R]) { await (await c.grantRole(await c.AGENT_ROLE(), agent.address)).wait(); }
  for (const a of [a1, a2, a3]) await (await V.grantRole(await V.APPROVER_ROLE(), a.address)).wait();
  await (await R.grantRole(await R.ADVISOR_ROLE(), a1.address)).wait();
  await (await T.mint(admin.address, 10n ** 12n)).wait();
  await (await T.approve(await V.getAddress(), 10n ** 12n)).wait();
  const g = (k, r) => { (res.ops[k] ||= []).push(Number(r.gas)); };
  let r = await timed(() => V.deposit(10n ** 11n)); g("deposit", r);
  r = await timed(() => V.createProgramme({minRiskBps:6000,minEngagementBps:5000,approvalsRequired:1,active:true,cooldown:30*24*3600,
      awardAmount:50000n,autoApproveLimit:50000n,perStudentCap:100000n,budget:10n**10n,committed:0n,rulesHash:id("retention-microgrant-v1")})); g("createProgramme", r);
  r = await timed(() => V.createProgramme({minRiskBps:7000,minEngagementBps:0,approvalsRequired:2,active:true,cooldown:0,
      awardAmount:300000n,autoApproveLimit:0n,perStudentCap:300000n,budget:10n**10n,committed:0n,rulesHash:id("emergency-aid-v1")})); g("createProgramme", r);
  const N = BT > 0 ? 20 : 100;
  const lat = { requestAward_auto: [], requestAward_pending: [], approve_final: [], logIntervention: [] };
  for (let i = 0; i < N; i++) {
    const p = id("bench|" + i); const w = rest[i % rest.length].address;
    r = await timed(() => V.registerStudent(p, w)); g("registerStudent", r);
    r = await timed(() => V.connect(agent).requestAward(1, p, 8000, 7000, id("ev" + i))); g("requestAward_autoDisburse", r); lat.requestAward_auto.push(r.ms);
    r = await timed(() => V.connect(agent).requestAward(2, p, 9000, 0, id("hv" + i))); g("requestAward_pending", r); lat.requestAward_pending.push(r.ms);
    const rid = 2 * i + 1;
    r = await timed(() => V.connect(a1).approve(rid)); g("approve_first", r);
    r = await timed(() => V.connect(a2).approve(rid)); g("approve_final_disburse", r); lat.approve_final.push(r.ms);
    r = await timed(() => R.connect(agent).logIntervention(p, 1, 8000, id("plan" + i), id("xgb-T1-v1"))); g("logIntervention", r); lat.logIntervention.push(r.ms);
    r = await timed(() => R.connect(a1).updateStatus(i, 3, id("out" + i))); g("updateStatus", r);
    if (i < 10) { r = await timed(() => V.connect(rest[i % rest.length]).fileAppeal(p, 2*i, id("appeal"))); }
  }
  // reject path (fresh request)
  { const p = id("rej"); await (await V.registerStudent(p, rest[0].address)).wait(); await (await V.connect(agent).requestAward(2, p, 9000, 0, id("x"))).wait();
    const last = (await V.totalRequests()) - 1n; r = await timed(() => V.connect(a3).reject(last, id("reason"))); g("reject", r); }
  r = await timed(() => R.connect(agent).anchorRiskSnapshot(id("merkle-root"), id("xgb-T1-v1"), 885)); g("anchorRiskSnapshot", r);
  for (const k in lat) res.latency[k] = stats(lat[k]);
  // batch logging
  for (const n of [1, 10, 25, 50, 100]) {
    const ids = [...Array(n)].map((_, j) => id("b" + n + "|" + j)); const kinds = ids.map(() => 1); const risks = ids.map(() => 7500); const plans = ids.map((_, j) => id("pl" + j));
    r = await timed(() => R.connect(agent).logBatch(ids, kinds, risks, plans, id("xgb-T1-v1")));
    res.batch[n] = { gas: Number(r.gas), gas_per_record: Number(r.gas) / n, ms: r.ms };
  }
  // end-to-end scenario from agent decisions on the hold-out cohort
  const D = JSON.parse(fs.readFileSync(OUT + "agent_decisions.json"));
  const t0 = process.hrtime.bigint(); let gasTotal = 0n, ok = 0, rejected = {}, pending = [];
  const pid = (sid) => id("salt-2026|" + sid);
  const sids = [...new Set(D.aid_requests.map(x => x.sid))];
  for (const s of sids) { const x = await timed(() => V.registerStudent(pid(s), rest[s % rest.length].address)); gasTotal += x.gas; }
  const iv = D.interventions; const B = 50; let ivGas = 0n;
  for (let k = 0; k < iv.length; k += B) { const ch = iv.slice(k, k + B);
    const x = await timed(() => R.connect(agent).logBatch(ch.map(c => pid(c.sid)), ch.map(c => c.kind), ch.map(c => c.riskBps), ch.map(c => "0x" + c.planHash), id(D.model_version)));
    ivGas += x.gas; }
  gasTotal += ivGas;
  let awardGas = 0n;
  for (const a of D.aid_requests) {
    try { const x = await timed(() => V.connect(agent).requestAward(a.programme, pid(a.sid), a.riskBps, a.engagementBps, "0x" + a.evidence));
      awardGas += x.gas; ok++; if (a.programme === 2) pending.push((await V.totalRequests()) - 1n); }
    catch (e) { const m = (e.shortMessage || e.message); const why = (m.match(/NotEligible\("([^"]+)"\)/) || [null, "other"])[1]; rejected[why] = (rejected[why] || 0) + 1; }
  }
  let apprGas = 0n;
  for (const rid of pending) { for (const s of [a1, a2]) { const x = await timed(() => V.connect(s).approve(rid)); apprGas += x.gas; } }
  gasTotal += awardGas + apprGas;
  res.scenario = { students_registered: sids.length, interventions_logged: iv.length, intervention_batches: Math.ceil(iv.length / B), intervention_gas: Number(ivGas),
    aid_requests: D.aid_requests.length, accepted_onchain: ok, rejected_onchain_by_rule: rejected, pending_requiring_approval: pending.length,
    award_gas: Number(awardGas), approval_gas: Number(apprGas), total_gas: Number(gasTotal), wall_s: Number(process.hrtime.bigint() - t0) / 1e9 };
  const summary = {}; for (const k in res.ops) summary[k] = stats(res.ops[k]); res.ops_summary = summary; delete res.ops;
  fs.writeFileSync(OUT + `chain_bench_bt${BT}.json`, JSON.stringify(res, null, 1));
  console.log(JSON.stringify({ deploy: res.deploy, ops: Object.fromEntries(Object.entries(summary).map(([k, v]) => [k, Math.round(v.mean)])), latency: res.latency, batch: res.batch, scenario: res.scenario }, null, 1));
}
main().catch((e) => { console.error(e); process.exit(1); });
