"""STRIVE - at-risk (dropout) prediction experiments on UCI dataset id 697
'Predict Students' Dropout and Academic Success' (Realinho et al., 2022).
All numbers written to results/ are produced by this script."""
import json, time, warnings, numpy as np, pandas as pd
from sklearn.model_selection import RepeatedStratifiedKFold, train_test_split, cross_validate
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import (roc_auc_score, average_precision_score, f1_score, recall_score,
    precision_score, balanced_accuracy_score, brier_score_loss, confusion_matrix, roc_curve,
    precision_recall_curve, f1_score)
from sklearn.calibration import calibration_curve
from sklearn.inspection import permutation_importance
from xgboost import XGBClassifier
warnings.filterwarnings("ignore")
SEED = 42
R = "../results/"
d = pd.read_csv("../data/data.csv", sep=";")
d.columns = [c.strip() for c in d.columns]
d["y"] = (d["Target"] == "Dropout").astype(int)

CAT = ["Marital status","Application mode","Course","Previous qualification","Nacionality",
       "Mother's qualification","Father's qualification","Mother's occupation","Father's occupation"]
ENROL = ["Marital status","Application mode","Application order","Course","Daytime/evening attendance",
 "Previous qualification","Previous qualification (grade)","Nacionality","Mother's qualification",
 "Father's qualification","Mother's occupation","Father's occupation","Admission grade","Displaced",
 "Educational special needs","Debtor","Tuition fees up to date","Gender","Scholarship holder",
 "Age at enrollment","International","Unemployment rate","Inflation rate","GDP"]
S1 = [c for c in d.columns if c.startswith("Curricular units 1st sem")]
S2 = [c for c in d.columns if c.startswith("Curricular units 2nd sem")]
STAGES = {"T0_enrolment": ENROL, "T1_after_sem1": ENROL+S1, "T2_after_sem2": ENROL+S1+S2}
SENSITIVE = ["Gender","Age at enrollment","Nacionality","Marital status","International"]

def prep(cols):
    cat = [c for c in cols if c in CAT]; num = [c for c in cols if c not in CAT]
    return ColumnTransformer([("cat", OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=10, sparse_output=False), cat),
                              ("num", StandardScaler(), num)])
pos_w = (d.y==0).sum()/(d.y==1).sum()
def models():
    return {
     "LR": LogisticRegression(max_iter=3000, class_weight="balanced", C=1.0),
     "RF": RandomForestClassifier(n_estimators=500, min_samples_leaf=2, class_weight="balanced_subsample", n_jobs=2, random_state=SEED),
     "XGB": XGBClassifier(n_estimators=400, learning_rate=0.05, max_depth=4, subsample=0.8, colsample_bytree=0.8,
                          scale_pos_weight=pos_w, eval_metric="logloss", random_state=SEED, n_jobs=2),
     "MLP": MLPClassifier(hidden_layer_sizes=(64,32), alpha=1e-3, max_iter=600, early_stopping=True, random_state=SEED)}

scoring = {"roc_auc":"roc_auc","pr_auc":"average_precision","f1":"f1","recall":"recall","precision":"precision",
           "bal_acc":"balanced_accuracy","brier":"neg_brier_score"}
cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=3, random_state=SEED)
rows=[]
for st, cols in STAGES.items():
    X=d[cols]; y=d.y
    for name, m in models().items():
        t=time.time()
        res = cross_validate(Pipeline([("p",prep(cols)),("m",m)]), X, y, cv=cv, scoring=scoring, n_jobs=1)
        row={"stage":st,"model":name,"n_features":len(cols),"fit_time_s":float(np.mean(res["fit_time"]))}
        for k in scoring:
            v=res["test_"+k]; v=-v if k=="brier" else v
            row[k+"_mean"]=float(np.mean(v)); row[k+"_std"]=float(np.std(v))
        rows.append(row); print(st,name,round(row["roc_auc_mean"],4),round(row["f1_mean"],4),round(time.time()-t,1),"s",flush=True)
cvdf=pd.DataFrame(rows); cvdf.to_csv(R+"cv_binary_stages.csv",index=False)

# 3-class benchmark at T2 (for comparison with dataset paper)
from sklearn.preprocessing import LabelEncoder
le=LabelEncoder(); y3=le.fit_transform(d.Target)
rows3=[]
cv3 = RepeatedStratifiedKFold(n_splits=5, n_repeats=3, random_state=SEED)
for name, m in [("LR",LogisticRegression(max_iter=3000,class_weight="balanced")),
                ("RF",RandomForestClassifier(n_estimators=500,min_samples_leaf=2,class_weight="balanced_subsample",n_jobs=2,random_state=SEED)),
                ("XGB",XGBClassifier(n_estimators=400,learning_rate=0.05,max_depth=4,subsample=0.8,colsample_bytree=0.8,random_state=SEED,n_jobs=2))]:
    cols=STAGES["T2_after_sem2"]
    res=cross_validate(Pipeline([("p",prep(cols)),("m",m)]), d[cols], y3, cv=cv3, scoring={"acc":"accuracy","f1_macro":"f1_macro","bal_acc":"balanced_accuracy"})
    rows3.append({"model":name,**{k+"_mean":float(np.mean(res["test_"+k])) for k in ["acc","f1_macro","bal_acc"]},
                  **{k+"_std":float(np.std(res["test_"+k])) for k in ["acc","f1_macro","bal_acc"]}})
pd.DataFrame(rows3).to_csv(R+"cv_3class_T2.csv",index=False); print(pd.DataFrame(rows3))

# Hold-out analysis for the early-warning operating point (T1, after first semester)
cols=STAGES["T1_after_sem1"]
Xtr,Xte,ytr,yte,itr,ite = train_test_split(d[cols], d.y, d.index, test_size=0.2, stratify=d.y, random_state=SEED)
out={"n_train":int(len(ytr)),"n_test":int(len(yte)),"test_dropout_rate":float(yte.mean())}
probs={}
for name in ["LR","XGB","RF"]:
    pl=Pipeline([("p",prep(cols)),("m",models()[name])]).fit(Xtr,ytr)
    probs[name]=pl.predict_proba(Xte)[:,1]
    if name=="XGB": best=pl
p=probs["XGB"]
out["holdout_auc"]={k:float(roc_auc_score(yte,v)) for k,v in probs.items()}
out["holdout_prauc"]={k:float(average_precision_score(yte,v)) for k,v in probs.items()}
# Threshold selection on TRAIN via inner CV (avoid test leakage): choose threshold reaching recall>=0.80 on OOF preds
from sklearn.model_selection import cross_val_predict, StratifiedKFold
oof=cross_val_predict(Pipeline([("p",prep(cols)),("m",models()["XGB"])]),Xtr,ytr,cv=StratifiedKFold(5,shuffle=True,random_state=SEED),method="predict_proba")[:,1]
ths=np.linspace(0.05,0.95,181)
rec=[recall_score(ytr,oof>=t) for t in ths]; f1s=[f1_score(ytr,oof>=t) for t in ths]
t_f1=float(ths[int(np.argmax(f1s))]); t_rec=float(max([t for t,r in zip(ths,rec) if r>=0.80]))
ops={}
for lab,t in [("default_0.5",0.5),("maxF1_oof",t_f1),("recall80_oof",t_rec)]:
    yp=(p>=t).astype(int); tn,fp,fn,tp=confusion_matrix(yte,yp).ravel()
    ops[lab]={"threshold":round(t,3),"precision":float(precision_score(yte,yp)),"recall":float(recall_score(yte,yp)),
              "f1":float(f1_score(yte,yp)),"flag_rate":float(yp.mean()),"tp":int(tp),"fp":int(fp),"fn":int(fn),"tn":int(tn)}
out["operating_points_XGB_T1"]=ops
# precision@k for advisor capacity
order=np.argsort(-p); yv=yte.values
out["precision_at_k"]={f"top{int(q*100)}%":{"k":int(round(q*len(p))),"precision":float(yv[order[:int(round(q*len(p)))]].mean()),
     "recall":float(yv[order[:int(round(q*len(p)))]].sum()/yv.sum())} for q in [0.05,0.10,0.20,0.30]}
out["brier_XGB_T1"]=float(brier_score_loss(yte,p))
fpr,tpr,_=roc_curve(yte,p); pr,rc,_=precision_recall_curve(yte,p)
fr,mp=calibration_curve(yte,p,n_bins=10,strategy="quantile")
json.dump({"roc":{k:[list(map(float,roc_curve(yte,v)[0])),list(map(float,roc_curve(yte,v)[1]))] for k,v in probs.items()},
           "calib":[list(map(float,mp)),list(map(float,fr))]},open(R+"curves.json","w"))
# fairness audit (on test, maxF1 threshold)
te=d.loc[ite].copy(); te["p"]=p; te["yp"]=(p>=t_f1).astype(int)
te["Age group"]=np.where(te["Age at enrollment"]<=23,"<=23",">23")
te["Gender_l"]=te["Gender"].map({1:"male",0:"female"}); te["Scholarship_l"]=te["Scholarship holder"].map({1:"holder",0:"non-holder"})
fair={}
for g in ["Gender_l","Age group","Scholarship_l"]:
    fair[g]={}
    for v,s in te.groupby(g):
        tn,fp,fn,tp=confusion_matrix(s.y,s.yp,labels=[0,1]).ravel()
        fair[g][v]={"n":int(len(s)),"base_rate":float(s.y.mean()),"selection_rate":float(s.yp.mean()),
                    "TPR":float(tp/(tp+fn)) if tp+fn else None,"FPR":float(fp/(fp+tn)) if fp+tn else None,
                    "AUC":float(roc_auc_score(s.y,s.p)) if s.y.nunique()>1 else None}
    vals=list(fair[g].values())
    fair[g]["DP_diff"]=abs(vals[0]["selection_rate"]-vals[1]["selection_rate"])
    fair[g]["EO_diff"]=max(abs(vals[0]["TPR"]-vals[1]["TPR"]),abs(vals[0]["FPR"]-vals[1]["FPR"]))
out["fairness_XGB_T1_maxF1"]=fair
# fairness-through-unawareness ablation
cols_u=[c for c in cols if c not in SENSITIVE]
plu=Pipeline([("p",prep(cols_u)),("m",models()["XGB"])]).fit(Xtr[cols_u],ytr); pu=plu.predict_proba(Xte[cols_u])[:,1]
te["ypu"]=(pu>=t_f1).astype(int)
unaw={"auc":float(roc_auc_score(yte,pu)),"f1":float(f1_score(yte,te.ypu))}
for g in ["Gender_l","Age group"]:
    sr=te.groupby(g).ypu.mean().values; tprs=[ (s.ypu[s.y==1]).mean() for _,s in te.groupby(g)]
    fprs=[(s.ypu[s.y==0]).mean() for _,s in te.groupby(g)]
    unaw[g]={"DP_diff":float(abs(sr[0]-sr[1])),"EO_diff":float(max(abs(tprs[0]-tprs[1]),abs(fprs[0]-fprs[1])))}
out["unawareness_ablation"]=unaw
# permutation importance
pi=permutation_importance(best,Xte,yte,scoring="roc_auc",n_repeats=10,random_state=SEED,n_jobs=2)
imp=pd.DataFrame({"feature":cols,"mean":pi.importances_mean,"std":pi.importances_std}).sort_values("mean",ascending=False)
imp.to_csv(R+"perm_importance_XGB_T1.csv",index=False)
# inference latency per student (agent scoring step)
t=time.perf_counter(); 
for _ in range(20): best.predict_proba(Xte)
out["inference_ms_per_student"]=float((time.perf_counter()-t)/20/len(Xte)*1000)
out["inference_ms_batch_885"]=float((time.perf_counter()-t)/20*1000)
json.dump(out,open(R+"holdout_T1.json","w"),indent=2)
# export risk scores for agent simulation
te[["p","y","Scholarship holder","Debtor","Tuition fees up to date","Curricular units 1st sem (approved)",
    "Curricular units 1st sem (enrolled)","Curricular units 1st sem (grade)","Age at enrollment","Gender"]].to_csv(R+"test_risk_scores.csv")
print(json.dumps({k:out[k] for k in ["holdout_auc","operating_points_XGB_T1","precision_at_k"]},indent=1))
