import os, json, requests, time, threading
from flask import Flask, request

TOKEN = os.getenv("TOKEN") or os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
DOSYA = "alarmlar.json"

def yukle():
    try:
        with open(DOSYA,"r") as f: return json.load(f)
    except: return {}
def kaydet(d):
    try:
        with open(DOSYA,"w") as f: json.dump(d,f)
    except: pass

manuel_alarm = yukle()

def tg(m):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id":CHAT_ID,"text":m}, timeout=10)
    except: pass

def fiyat_al(sym):
    sym=sym.upper()
    for s in [sym, sym.replace("USDT",""), sym.replace("USDT","")+"USDT"]:
        for cat in ["linear","spot"]:
            try:
                r=requests.get(f"https://api.bybit.com/v5/market/tickers?category={cat}&symbol={s}", timeout=6).json()
                if r.get('retCode')==0 and r.get('result',{}).get('list'):
                    return float(r['result']['list'][0]['lastPrice'])
            except: pass
    return None

def seviye_al(a):
    # hem eski {"fiyat":...} hem yeni 0.28 formatini anla
    if isinstance(a, dict): return float(a.get('fiyat',0))
    try: return float(a)
    except: return None

app = Flask(__name__)
@app.route('/')
def home(): return "Bot aktif"
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data=request.get_json(force=True,silent=True) or {}
        tg(f"📈 {data}")
        return "OK",200
    except: return "OK",200

def run_web(): app.run(host="0.0.0.0", port=int(os.getenv("PORT",10000)))
threading.Thread(target=run_web, daemon=True).start()

tg("✅ Bot aktif")
offset=0
while True:
    try:
        r=requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={offset}&timeout=10", timeout=15).json()
        for upd in r.get('result',[]):
            offset=upd['update_id']+1
            raw=upd.get('message',{}).get('text','').strip()
            if not raw: continue
            up=raw.upper()
            if up=="LISTE":
                out=[]
                for k,v in manuel_alarm.items():
                    for a in v:
                        out.append(f"{k} {seviye_al(a)}")
                tg("📋 " + "\n".join(out) if out else "Liste bos")
            elif up.startswith("SIL"):
                p=up.split()
                if len(p)>1:
                    c=p[1].upper()
                    manuel_alarm.pop(c,None)
                    manuel_alarm.pop(c[:-4] if c.endswith("USDT") else c+"USDT",None)
                else: manuel_alarm={}
                kaydet(manuel_alarm)
                tg("🗑️ Silindi")
            else:
                parca=raw.split()
                if len(parca)>=2:
                    coin=parca[0].upper()
                    if "USDT" not in coin: coin=coin+"USDT"
                    try: fiyat=float(parca[1].replace(",","."))
                    except: continue
                    if coin not in manuel_alarm: manuel_alarm[coin]=[]
                    manuel_alarm[coin].append(fiyat)
                    kaydet(manuel_alarm)
                    tg(f"✅ {coin} {fiyat} eklendi")
    except: pass

    for coin, alarmlar in list(manuel_alarm.items()):
        f=fiyat_al(coin)
        if not f: continue
        for a in alarmlar[:]:
            sev=seviye_al(a)
            if not sev: continue
            # %0.5 icine girerse cal - ziplasa da yakalar
            if abs(f - sev) / sev < 0.005:
                for i in range(3):
                    tg(f"🔔 {coin} {sev} GELDI! ${f} {i+1}/3")
                    time.sleep(1)
                manuel_alarm[coin].remove(a)
                if not manuel_alarm[coin]: del manuel_alarm[coin]
                kaydet(manuel_alarm)
    time.sleep(3)
