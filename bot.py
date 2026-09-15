import os, json, requests, time, threading
from flask import Flask

TOKEN = os.getenv("TOKEN") or os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
DOSYA = "alarmlar.json"

def yukle():
    try:
        with open(DOSYA,"r") as f: return json.load(f)
    except: return {}
def kaydet(d):
    with open(DOSYA,"w") as f: json.dump(d,f)

alarmlar = yukle()
son = {}

def tg(t):
    try: requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={"chat_id":CHAT_ID,"text":t}, timeout=10)
    except: pass

def fiyat(sym):
    sym = sym.upper()
    for s in [sym, sym.replace("USDT","")]:
        for cat in ["linear","spot"]:
            try:
                r = requests.get(f"https://api.bybit.com/v5/market/tickers?category={cat}&symbol={s}", timeout=5).json()
                if r.get("result",{}).get("list"):
                    return float(r["result"]["list"][0]["lastPrice"])
            except: pass
    return None

def sev(a):
    if isinstance(a, dict): return float(a.get("fiyat") or a.get("f") or 0)
    try: return float(a)
    except: return None

try: requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook?drop_pending_updates=True", timeout=5)
except: pass

app = Flask(__name__)
@app.route("/")
def h(): return "ok"
threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.getenv("PORT",10000))), daemon=True).start()

tg("✅ Bot aktif")
offset = 0

while True:
    try:
        res = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={offset}&timeout=10", timeout=15).json()
        for u in res.get("result",[]):
            offset = u["update_id"]+1
            txt = u.get("message",{}).get("text","").strip()
            if not txt: continue
            up = txt.upper()
            if up == "LISTE":
                l = [f"{k} {sev(x)}" for k,v in alarmlar.items() for x in v]
                tg("\n".join(l) if l else "Liste boş")
            elif up.startswith("SIL"):
                p = up.split()
                if len(p)>1:
                    c = p[1].upper()
                    if "USDT" not in c: c+="USDT"
                    alarmlar.pop(c,None)
                else: alarmlar={}
                kaydet(alarmlar)
                tg("🗑️ Silindi")
            else:
                pr = txt.split()
                if len(pr)>=2:
                    coin = pr[0].upper()
                    if "USDT" not in coin: coin+="USDT"
                    try: f = float(pr[1].replace(",","."))
                    except: continue
                    if coin not in alarmlar: alarmlar[coin]=[]
                    if not any(abs((sev(x) or 0)-f) < 0.000001 for x in alarmlar[coin]):
                        alarmlar[coin].append(f)
                        kaydet(alarmlar)
                        tg(f"✅ {coin} {f} eklendi")
    except: pass

    for coin, lst in list(alarmlar.items()):
        pf = fiyat(coin)
        if not pf: continue
        last = son.get(coin)
        son[coin]=pf
        for a in lst[:]:
            s = sev(a)
            if not s: continue
            if abs(pf-s)/s < 0.005 or (last and (last-s)*(pf-s) <=0):
                for i in range(3):
                    tg(f"🔔 {coin} {s} GELDI! ${pf}")
                    time.sleep(0.7)
                alarmlar[coin].remove(a)
                if not alarmlar[coin]: del alarmlar[coin]
                kaydet(alarmlar)
    time.sleep(2)
