"""S07: VAL grid for the dip-buy spec (val is where 10-10 is absent = honest test).
Compare breadth {16,18,20} x chg{<=-2.5} x horizon{f60,f240,f1440} on VAL.
Pick the spec by val mean+significance+val-maxday. Report dev(no1010) alongside for context.
"""
import numpy as np, pandas as pd
from _harness import load, seg, net_return, cell_stats, bh_fdr

df = load()
dev=seg(df,"dev").copy(); val=seg(df,"val").copy()
dev_no=dev[dev["day"]!="2025-10-10"]

rows=[]
for bth in [16,18,20]:
    for ret in ["f60","f240","f1440"]:
        mv=(val["breadth_min"]>=bth)&(val["chg"]<=-2.5)
        vs=val[mv].copy()
        if len(vs)<50:
            continue
        vs["net"]=net_return(vs[ret].values,vs["atr_pct"].values,"long")
        vst=cell_stats(vs,"net",f"b{bth}_{ret}")
        # dev no-1010 context
        md=(dev_no["breadth_min"]>=bth)&(dev_no["chg"]<=-2.5)
        ds=dev_no[md].copy(); ds["net"]=net_return(ds[ret].values,ds["atr_pct"].values,"long")
        dst=cell_stats(ds,"net","dev")
        rows.append({"label":f"b{bth}_c-2.5_{ret}","bth":bth,"ret":ret,
            "dev_n":dst["n"],"dev_mean":dst["net_mean"],"dev_med":dst["net_median"],"dev_win":dst["winrate"],"dev_maxday":dst["max_one_day_frac"],
            "val_n":vst["n"],"val_mean":vst["net_mean"],"val_med":vst["net_median"],"val_win":vst["winrate"],"val_p":vst["p"],"val_maxday":vst["max_one_day_frac"],"val_dropTop":vst["mean_drop_topday"],"val_ndays":vst["n_days"]})
res=pd.DataFrame(rows)
res["val_q"]=bh_fdr(res["val_p"].values)
res=res.sort_values("val_mean",ascending=False)
pd.set_option("display.width",250); pd.set_option("display.max_columns",40)
print("DEV(no-1010) vs VAL — dip-buy grid (sorted by val_mean):")
print(res[["label","dev_n","dev_mean","dev_med","dev_win","val_n","val_mean","val_med","val_win","val_p","val_q","val_maxday","val_dropTop","val_ndays"]].round(3).to_string(index=False))

print("\nInterpretation guide: want val_mean>0, val_q<0.10, val_maxday<0.5, dev sign matches.")
