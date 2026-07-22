import json, os, time, urllib.request
from datetime import date, timedelta
UW = os.environ["UNUSUAL_WHALES_API_KEY"]; FRED = os.environ["FRED_API_KEY"]
def get(url, hdr=None, tries=3):
    for i in range(tries):
        try:
            h=dict(hdr or {}); h.setdefault("User-Agent","Mozilla/5.0")
            req = urllib.request.Request(url, headers=h)
            return json.loads(urllib.request.urlopen(req, timeout=25).read().decode())
        except Exception as e:
            if i < tries-1: time.sleep(3); continue
            return {"_err": str(e)[:100]}
# 断点: 已拉过的(date,session)
done = set()
P = "data/uw_earnings_events.jsonl"
if os.path.exists(P):
    for l in open(P):
        try:
            d0 = json.loads(l); done.add((d0.get("_date"), d0.get("_session")))
        except: pass
out = open(P, "a")
d = date(2026,3,2); today = date(2026,7,2); n=0
while d <= today:
    if d.weekday() < 5:
        for sess in ("afterhours","premarket"):
            if (d.isoformat(), sess) in done: continue
            r = get("https://api.unusualwhales.com/api/earnings/%s?date=%s&limit=200"%(sess,d.isoformat()),
                    {"Authorization":"Bearer "+UW})
            if "_err" in r:
                print("ERR %s %s: %s"%(d,sess,r["_err"]), flush=True); time.sleep(2); continue
            rows = r.get("data") or []
            if not rows:
                out.write(json.dumps({"_date":d.isoformat(),"_session":sess,"_empty":True})+"\n")
            for ev in rows:
                ev["_date"]=d.isoformat(); ev["_session"]=sess
                out.write(json.dumps(ev)+"\n"); n+=1
            out.flush(); time.sleep(0.5)
    d += timedelta(days=1)
out.close()
print("UW新增事件: %d"%n, flush=True)
rel = {"CPI":10,"NFP":50,"PCE":54}; cal={}
for name,rid in rel.items():
    r=get("https://api.stlouisfed.org/fred/release/dates?release_id=%d&api_key=%s&file_type=json&realtime_start=2026-01-01&sort_order=asc"%(rid,FRED))
    cal[name]=[x["date"] for x in r.get("release_dates",[])]
cal["FOMC"]=["2026-01-28","2026-03-18","2026-04-29","2026-06-17","2026-07-29","2026-09-16","2026-10-28","2026-12-09"]
cal["_times_et"]={"CPI":"08:30","NFP":"08:30","PCE":"08:30","FOMC":"14:00"}
json.dump(cal, open("data/macro_calendar.json","w"), indent=1)
print("宏观日历OK", flush=True)
print("EVENTS_PULL_DONE", flush=True)
