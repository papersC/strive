import json, os, numpy as np, pandas as pd, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
R="../results/"; F="../figures/"
plt.rcParams.update({"font.size":10,"axes.spines.top":False,"axes.spines.right":False})
cv=pd.read_csv(R+"cv_binary_stages.csv")
# Fig3: AUC and F1 by stage
fig,axs=plt.subplots(1,2,figsize=(11,4))
st=["T0_enrolment","T1_after_sem1","T2_after_sem2"]; lab=["T0 (enrolment)","T1 (after sem. 1)","T2 (after sem. 2)"]
models=["LR","RF","XGB","MLP"]; w=0.2
for ax,met,nm in [(axs[0],"roc_auc","ROC-AUC"),(axs[1],"f1","F1 (dropout class)")]:
    for i,m in enumerate(models):
        s=cv[cv.model==m].set_index("stage").loc[st]
        ax.bar(np.arange(3)+(i-1.5)*w,s[met+"_mean"],w,yerr=s[met+"_std"],capsize=3,label=m)
    ax.set_xticks(range(3)); ax.set_xticklabels(lab); ax.set_ylabel(nm); ax.set_ylim(0.5 if met=="f1" else 0.75,0.95 if met=="roc_auc" else 0.85)
axs[0].legend(ncol=4,fontsize=8,loc="upper left")
plt.tight_layout(); plt.savefig(F+"fig3_stage_performance.png",dpi=300); plt.close()
# Fig4: ROC + calibration
c=json.load(open(R+"curves.json")); h=json.load(open(R+"holdout_T1.json"))
fig,axs=plt.subplots(1,2,figsize=(10,4.2))
for k,(fp,tp) in c["roc"].items(): axs[0].plot(fp,tp,label=f"{k} (AUC = {h['holdout_auc'][k]:.3f})")
axs[0].plot([0,1],[0,1],"k--",lw=0.8); axs[0].set_xlabel("False positive rate"); axs[0].set_ylabel("True positive rate"); axs[0].legend(); axs[0].set_title("(a) ROC, hold-out set, stage T1")
mp,fr=c["calib"]; axs[1].plot(mp,fr,"o-",label=f"XGB (Brier = {h['brier_XGB_T1']:.3f})"); axs[1].plot([0,1],[0,1],"k--",lw=0.8)
axs[1].set_xlabel("Mean predicted risk"); axs[1].set_ylabel("Observed dropout fraction"); axs[1].legend(); axs[1].set_title("(b) Reliability diagram (deciles)")
plt.tight_layout(); plt.savefig(F+"fig4_roc_calibration.png",dpi=300); plt.close()
# Fig5: permutation importance + precision@k
imp=pd.read_csv(R+"perm_importance_XGB_T1.csv").head(10)[::-1]
fig,axs=plt.subplots(1,2,figsize=(11.5,4.2),gridspec_kw={"width_ratios":[1.4,1]})
axs[0].barh(imp.feature,imp["mean"],xerr=imp["std"],color="#4c72b0"); axs[0].set_xlabel("Decrease in ROC-AUC when permuted"); axs[0].set_title("(a) Top-10 permutation importance (XGB, T1)")
pk=h["precision_at_k"]; ks=list(pk); x=np.arange(len(ks))
axs[1].bar(x-0.2,[pk[k]["precision"] for k in ks],0.4,label="Precision"); axs[1].bar(x+0.2,[pk[k]["recall"] for k in ks],0.4,label="Recall")
axs[1].set_xticks(x); axs[1].set_xticklabels([k.replace("top","Top ") for k in ks]); axs[1].set_ylim(0,1.08); axs[1].legend(); axs[1].set_title("(b) Advisor-capacity view: precision/recall@k")
plt.tight_layout(); plt.savefig(F+"fig5_importance_capacity.png",dpi=300); plt.close()
# Fig6: fairness
fa=h["fairness_XGB_T1_maxF1"]
fig,axs=plt.subplots(1,3,figsize=(12,3.8),sharey=True)
for ax,(g,t) in zip(axs,[("Gender_l","Gender"),("Age group","Age at enrolment"),("Scholarship_l","Scholarship status")]):
    grp=[k for k in fa[g] if k not in ("DP_diff","EO_diff")]; x=np.arange(3)
    for i,v in enumerate(grp):
        ax.bar(x+(i-0.5)*0.38,[fa[g][v]["selection_rate"],fa[g][v]["TPR"],fa[g][v]["FPR"]],0.38,label=f"{v} (n={fa[g][v]['n']}, base={fa[g][v]['base_rate']:.2f})")
    ax.set_ylim(0,1.25); ax.set_xticks(x); ax.set_xticklabels(["Selection\nrate","TPR","FPR"]); ax.set_title(f"{t}\nDP gap={fa[g]['DP_diff']:.3f}, EO gap={fa[g]['EO_diff']:.3f}",fontsize=9.5); ax.legend(fontsize=7.5,loc="upper left")
plt.tight_layout(); plt.savefig(F+"fig6_fairness.png",dpi=300); plt.close()
# Fig7: gas
b=json.load(open(R+"chain_bench_bt0.json")); o=b["ops_summary"]
order=[("registerStudent","registerStudent"),("requestAward_autoDisburse","requestAward (auto-disburse)"),("requestAward_pending","requestAward (pending)"),
 ("approve_first","approve (1st of 2)"),("approve_final_disburse","approve (final, disburse)"),("reject","reject"),("logIntervention","logIntervention"),
 ("updateStatus","updateStatus"),("anchorRiskSnapshot","anchorRiskSnapshot"),("createProgramme","createProgramme"),("deposit","deposit")]
fig,axs=plt.subplots(1,2,figsize=(12,4.3),gridspec_kw={"width_ratios":[1.5,1]})
vals=[o[k]["mean"]/1000 for k,_ in order]; axs[0].barh([l for _,l in order][::-1],vals[::-1],color="#dd8452")
for i,v in enumerate(vals[::-1]): axs[0].text(v+2,i,f"{v:.1f}k",va="center",fontsize=8)
axs[0].set_xlabel("Gas used (thousands), mean over runs"); axs[0].set_title("(a) Gas per operation")
bs=b["batch"]; n=[int(k) for k in bs]; axs[1].plot(n,[bs[k]["gas_per_record"]/1000 for k in bs],"o-")
axs[1].axhline(o["logIntervention"]["mean"]/1000,ls="--",color="grey",label="single logIntervention")
axs[1].set_xscale("log"); axs[1].set_xlabel("Batch size (records)"); axs[1].set_ylabel("Gas per record (thousands)"); axs[1].legend(); axs[1].set_title("(b) Batched intervention logging")
plt.tight_layout(); plt.savefig(F+"fig7_gas.png",dpi=300); plt.close()
# Fig8: latency
fig,ax=plt.subplots(figsize=(8,3.8)); files=[("chain_bench_bt0.json","automine"),("chain_bench_bt2000.json","2 s block interval")]
ops=["requestAward_auto","requestAward_pending","approve_final","logIntervention"]; x=np.arange(len(ops)); i=0
for f,l in files:
    if not os.path.exists(R+f): continue
    L=json.load(open(R+f))["latency"]
    ax.bar(x+(i-0.5)*0.38,[L[k]["p50"] for k in ops],0.38,yerr=[[0]*4,[L[k]["p95"]-L[k]["p50"] for k in ops]],capsize=3,label=f"{l} (median, whisker = p95)"); i+=1
ax.set_yscale("log"); ax.set_xticks(x); ax.set_xticklabels(["requestAward\n(auto)","requestAward\n(pending)","approve\n(final)","logIntervention"]); ax.set_ylabel("Submit-to-receipt latency (ms)"); ax.legend(fontsize=8)
plt.tight_layout(); plt.savefig(F+"fig8_latency.png",dpi=300); plt.close(); print("done")
