"""STRIVE multi-agent orchestration prototype (rule-based planner) run on hold-out risk scores.
Produces agent decisions consumed by the on-chain benchmark (contracts/scripts/bench.js).
NOTE: student engagement with interventions is NOT in the dataset and is SIMULATED (Beta(4,3), seed 7)."""
import json, hashlib, numpy as np, pandas as pd, time
from dataclasses import dataclass, asdict
R="/workspace/papers/paper5/results/"
H=json.load(open(R+"holdout_T1.json"))
T_HIGH=0.70; T_MED=H["operating_points_XGB_T1"]["maxF1_oof"]["threshold"]   # medium tier = max-F1 threshold from OOF
ADVISOR_CAPACITY=0.10   # advisors can contact at most 10% of the cohort per cycle
MODEL_VERSION="xgb-T1-v1"

@dataclass
class Plan: sid:int; risk:float; tier:str; actions:list; aid_programme:int; rationale:str

class MonitorAgent:
    def observe(self, df): return df            # in deployment: pulls LMS/SIS features via xAPI/LRS
class RiskAnalystAgent:
    def assess(self, df): return df.assign(tier=np.select([df.p>=T_HIGH, df.p>=T_MED],["high","medium"],"low"))
class InterventionPlannerAgent:
    def plan(self, df):
        cap=int(round(ADVISOR_CAPACITY*len(df))); plans=[]
        ranked=df.sort_values("p",ascending=False); advisor_slots=set(ranked.index[:cap])
        for i,r in df.iterrows():
            if r.tier=="low": continue
            acts=[]; why=[]
            if i in advisor_slots: acts.append("AdvisorAlert"); why.append("top-decile risk")
            sem_ratio = r["Curricular units 1st sem (approved)"]/max(r["Curricular units 1st sem (enrolled)"],1)
            if sem_ratio<0.75: acts.append("TutoringReferral"); why.append(f"approved/enrolled={sem_ratio:.2f}")
            need = (r.Debtor==1) or (r["Tuition fees up to date"]==0)
            if need: acts.append("FinancialCounselling"); why.append("arrears/debt")
            if not acts: acts.append("PeerMentoring"); why.append("medium risk, no specific trigger")
            prog = 2 if (need and r.p>=T_HIGH and r.Debtor==1) else (1 if (need or r["Scholarship holder"]==1) and r.p>=0.60 else 0)
            plans.append(Plan(int(i),float(r.p),r.tier,acts,prog,"; ".join(why)))
        return plans
class AidCoordinatorAgent:
    def __init__(self, seed=7): self.rng=np.random.default_rng(seed)
    def requests(self, plans):
        out=[]
        for pl in plans:
            if pl.aid_programme==0: continue
            eng=float(self.rng.beta(4,3))        # SIMULATED engagement with the planned intervention
            out.append({"sid":pl.sid,"programme":pl.aid_programme,"riskBps":int(round(pl.risk*10000)),"engagementBps":int(round(eng*10000)),
                        "evidence":hashlib.sha256(json.dumps(asdict(pl),sort_keys=True).encode()).hexdigest()})
        return out

t=time.perf_counter()
df=pd.read_csv(R+"test_risk_scores.csv",index_col=0)
df=RiskAnalystAgent().assess(MonitorAgent().observe(df))
plans=InterventionPlannerAgent().plan(df)
reqs=AidCoordinatorAgent().requests(plans)
elapsed=(time.perf_counter()-t)*1000
kinds={"AdvisorAlert":0,"TutoringReferral":1,"WellbeingReferral":2,"FinancialCounselling":3,"PeerMentoring":4}
interventions=[{"sid":p.sid,"kind":kinds[a],"riskBps":int(round(p.risk*10000)),
                "planHash":hashlib.sha256(f"{p.sid}|{a}|{p.rationale}".encode()).hexdigest()} for p in plans for a in p.actions]
summ={"cohort":len(df),"tiers":df.tier.value_counts().to_dict(),"plans":len(plans),"interventions":len(interventions),
      "by_kind":pd.Series([a for p in plans for a in p.actions]).value_counts().to_dict(),
      "aid_requests":len(reqs),"aid_by_programme":pd.Series([r["programme"] for r in reqs]).value_counts().to_dict() if reqs else {},
      "eligible_by_engagement_prog1":sum(1 for r in reqs if r["programme"]==1 and r["engagementBps"]>=5000),
      "true_dropouts_in_high":int(df[df.tier=="high"].y.sum()),"n_high":int((df.tier=="high").sum()),
      "true_dropouts_in_medium":int(df[df.tier=="medium"].y.sum()),"n_medium":int((df.tier=="medium").sum()),
      "dropouts_total":int(df.y.sum()),"orchestration_ms":elapsed,"thresholds":{"high":T_HIGH,"medium":T_MED}}
json.dump({"model_version":MODEL_VERSION,"interventions":interventions,"aid_requests":reqs,"summary":summ},open(R+"agent_decisions.json","w"),indent=1)
print(json.dumps(summ,indent=1))
