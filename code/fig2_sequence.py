import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
F="../figures/"
# ---------------- Figure 2: sequence diagram
fig,ax=plt.subplots(figsize=(14,8.6)); ax.axis("off")
actors=["LMS/SIS","Monitor\nAgent","Risk Analyst\nAgent","Planner\nAgent","Advisor\n(human)","Aid Coord.\nAgent","Intervention\nRegistry","SupportFund\nVault","Committee\n(M-of-N)","Student"]
xs=[i*1.4 for i in range(len(actors))]; top=0; bottom=-17.2
ax.set_xlim(-0.7,xs[-1]+0.7); ax.set_ylim(bottom-0.3,1.2)
for x,a in zip(xs,actors):
    c="#fff1c1" if a in ("Intervention\nRegistry","SupportFund\nVault") else ("#fde2e4" if a in ("Advisor\n(human)","Committee\n(M-of-N)","Student") else "#e2ece9")
    ax.add_patch(FancyBboxPatch((x-0.6,0.15),1.2,0.85,boxstyle="round,pad=0.02",fc=c,ec="#333"))
    ax.text(x,0.575,a,ha="center",va="center",fontsize=8.3,fontweight="bold")
    ax.plot([x,x],[0.15,bottom],ls="--",color="#999",lw=0.8)
msgs=[(0,1,"1  nightly xAPI / grade / fee feed (pseudonymised)"),(1,2,"2  feature vector at stage T1"),
      (2,2,"3  score p, reason codes, fairness check"),(2,3,"4  risk tier (high / medium)"),
      (3,6,"5  logBatch(pseudoIds, kinds, risk, planHash)"),(3,4,"6  advisor alert (top-decile capacity)"),
      (4,9,"7  outreach meeting / tutoring referral"),(4,6,"8  updateStatus(id, Completed, outcomeHash)"),
      (3,5,"9  aid-eligible plan (need + risk)"),(5,7,"10  requestAward(prog, pid, risk, engagement, evidence)"),
      (7,7,"11  on-chain rule check: risk, engagement, cap, cooldown, budget"),(7,9,"12a  auto-disburse micro-grant (<= limit)"),
      (7,8,"12b  AwardRequested (pending, > limit)"),(8,7,"13  approve() x M"),(7,9,"14  AwardDisbursed (token transfer)"),
      (9,7,"15  fileAppeal(pid, requestId, reasonHash)"),(6,2,"16  outcomes feed back for model monitoring")]
for (y0,y1,lab,c) in [(-0.9,-4.4,"Detect","#eef5ff"),(-4.4,-8.3,"Intervene","#eefaf2"),(-8.3,-15.2,"Support funds","#fff8e6"),(-15.2,-17.2,"Contest / learn","#fbeef0")]:
    ax.axhspan(y1,y0,color=c,zorder=-5); ax.text(-0.68,(y0+y1)/2,lab,rotation=90,va="center",fontsize=9,fontweight="bold",color="#555")
y=-0.5
for a,b,t in msgs:
    y-=0.98
    if a==b:
        ax.add_patch(FancyArrowPatch((xs[a],y+0.2),(xs[a],y-0.25),connectionstyle="arc3,rad=-1.6",arrowstyle="-|>",mutation_scale=10,color="#225"))
        ax.text(xs[a]+0.35,y,t,fontsize=8,va="center")
    else:
        col="#8a5a00" if b in (6,7) or a in (6,7) else "#225"
        ax.add_patch(FancyArrowPatch((xs[a],y),(xs[b],y),arrowstyle="-|>",mutation_scale=11,color=col,lw=1.3))
        span=abs(xs[a]-xs[b])
        if span>4: ax.text((xs[a]+xs[b])/2,y+0.17,t,ha="center",fontsize=8.3,bbox=dict(fc="white",ec="none",pad=0.5))
        else: ax.text(min(xs[a],xs[b])+0.05,y+0.17,t,ha="left",fontsize=8.3,bbox=dict(fc="white",ec="none",pad=0.5))
plt.savefig(F+"fig2_sequence.png",dpi=300,bbox_inches="tight"); plt.close()
print("ok")
