import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
F="/workspace/papers/paper5/figures/"
def box(ax,x,y,w,h,txt,fc="white",ec="#333",fs=8.5,bold=False):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=0.004,rounding_size=0.01",fc=fc,ec=ec,lw=1))
    ax.text(x+w/2,y+h/2,txt,ha="center",va="center",fontsize=fs,fontweight="bold" if bold else "normal")
def layer(ax,x,y,w,h,t,c):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=0.003,rounding_size=0.01",fc=c,ec="#666",lw=1.2))
    ax.text(x+0.01,y+h-0.012,t,fontsize=10,fontweight="bold",va="top")
def arr(ax,x1,y1,x2,y2,t="",c="#333",lx=None,ly=None,ha="left"):
    ax.add_patch(FancyArrowPatch((x1,y1),(x2,y2),arrowstyle="-|>",mutation_scale=13,color=c,lw=1.5,zorder=5))
    if t: ax.text(lx if lx is not None else (x1+x2)/2+0.006, ly if ly is not None else (y1+y2)/2,t,fontsize=7.8,color=c,va="center",ha=ha,fontweight="bold",zorder=6,bbox=dict(fc="white",ec=c,lw=0.6,pad=0.15,boxstyle="round"))
fig,ax=plt.subplots(figsize=(13,9)); ax.set_xlim(0,1.0); ax.set_ylim(0,1.0); ax.axis("off")
W=0.56; X=0.01; bw=(W-0.02-0.04)/5
L=[(0.78,"L4  Stakeholder layer (human authority)","#fde2e4"),(0.53,"L3  Agentic orchestration layer","#e2ece9"),
   (0.28,"L2  Predictive analytics layer","#dfe7fd"),(0.03,"L1  Data and integration layer","#ece4f7")]
for y,t,c in L: layer(ax,X,y,W,0.21,t,c)
xs=[X+0.01+i*(bw+0.01) for i in range(5)]
for x,t in zip(xs,["Students\n(app, wallet,\nappeals)","Advisors\n& tutors","Programme\nleaders","Financial-aid\ncommittee\n(M-of-N)","Auditors /\nregulators"]): box(ax,x,0.795,bw,0.15,t)
for x,t in zip(xs,["Monitor\nAgent","Risk Analyst\nAgent","Intervention\nPlanner\nAgent","Aid\nCoordinator\nAgent","Compliance\n& Audit\nAgent"]): box(ax,x,0.6,bw,0.095,t,bold=True,fs=8.3)
box(ax,xs[0],0.54,2*bw+0.01,0.052,"Case memory (off-chain, encrypted)",fc="#f6fbf9",fs=8)
box(ax,xs[2],0.54,2*bw+0.01,0.052,"Guardrails, tool registry,\noptional LLM drafting",fc="#f6fbf9",fs=8)
box(ax,xs[4],0.54,bw,0.052,"HITL console",fc="#f6fbf9",fs=8)
for x,t in zip(xs,["Feature store\n(T0/T1/T2\nstages)","Risk model\n(XGBoost)","Explanations\n(reason\ncodes)","Fairness &\ndrift monitor","Model\nregistry\n(versioned)"]): box(ax,x,0.292,bw,0.15,t)
for x,t in zip(xs,["LMS / VLE\n(xAPI\nclickstream)","Student info.\nsystem\n(grades)","Finance\nsystem\n(fees, debt)","Advising /\nCRM\nrecords","Consent &\npseudonym.\ngateway"]): box(ax,x,0.042,bw,0.15,t)
# blockchain column
BX=0.645; BW=0.19
layer(ax,BX,0.28,BW,0.71,"Blockchain trust\nlayer","#fff1c1")
box(ax,BX+0.01,0.755,BW-0.02,0.14,"InterventionRegistry\n(plan / status /\noutcome hashes,\nMerkle risk snapshots)",fs=8)
box(ax,BX+0.01,0.555,BW-0.02,0.17,"SupportFundVault\n(programmes, on-chain\neligibility, caps,\ncooldown, M-of-N,\nappeals)",fs=8)
box(ax,BX+0.01,0.43,BW-0.02,0.095,"Aid token (ERC-20,\nfiat-backed)",fs=8)
box(ax,BX+0.01,0.30,BW-0.02,0.105,"Permissioned EVM\n(Besu / QBFT);\nevent log = audit trail",fs=8)
# cross-cutting
CX=0.85; CW=0.145
layer(ax,CX,0.03,CW,0.96,"Cross-cutting\ncontrols","#f2f2f2")
items=["Privacy by design:\nno PII on-chain,\nsalted pseudonyms","Role-based\naccess control","Explainability &\ncontestability","Fairness audits\n(DP / EO gaps)","Security: pause,\nre-entrancy guard,\nstatic analysis","Governance:\nEU AI Act,\nUAE PDPL"]
for i,t in enumerate(items): box(ax,CX+0.01,0.80-i*0.13,CW-0.02,0.11,t,fs=7.8)
# arrows
arr(ax,xs[0]+bw/2,0.192,xs[0]+bw/2,0.292,"features",lx=xs[0]+bw/2+0.008,ly=0.245)
arr(ax,xs[1]+bw/2,0.442,xs[1]+bw/2,0.54,"risk score + reasons",lx=xs[1]+bw/2+0.008,ly=0.49)
arr(ax,xs[4]+bw/2,0.442,xs[4]+bw/2,0.54,"outcome monitoring",lx=xs[4]+bw/2-0.008,ly=0.49,ha="right")
arr(ax,xs[2]+bw/2,0.695,xs[1]+bw/2,0.795,"alerts / referrals",c="#223377",lx=xs[1]+bw/2-0.005,ly=0.745,ha="right")
arr(ax,xs[3]+bw/2,0.695,xs[3]+bw/2,0.795,"HITL review",c="#223377",lx=xs[3]+bw/2+0.008,ly=0.745)
arr(ax,X+W,0.67,BX+0.01,0.80,"logBatch()",c="#8a5a00",lx=X+W+0.004,ly=0.755)
arr(ax,X+W,0.63,BX+0.01,0.63,"requestAward()",c="#8a5a00",lx=X+W+0.002,ly=0.655)
arr(ax,BX+0.01,0.87,X+W,0.87,"events",c="#8a5a00",lx=X+W+0.012,ly=0.895)
plt.savefig(F+"fig1_architecture.png",dpi=300,bbox_inches="tight"); plt.close(); print("ok")
