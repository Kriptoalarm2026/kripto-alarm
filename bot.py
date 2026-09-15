import os, json, requests, time, threading
from flask import Flask, request

TOKEN = os.getenv("TOKEN") or os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
DOSYA = "alarmlar.json"
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL") or "https://kripto-alarm-0rqu.onrender.com"

def yukle():
    try:
        with open(DOSYA, "r") as f: return json.load(f)
    except: return {}
def kaydet(d):
    try:
        with open(DOSYA, "w") as f: json.dump(d, f)
    except: pass

manuel_alarm = yukle()
son_fiyat = {}

def tg(mesaj):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": mesaj, "parse_mode":"Markdown"}, timeout=10)
    except: pass

def fiyat_al(sym):
    headers = {"User-Agent": "Mozilla/5.0"}
    for cat in ["spot","linear"]:
        try:
            r = requests.get(f"https://api.bybit.com/v5/market/tickers?category={cat}&symbol={sym}", headers=headers, timeout=6).json()
            if r.get('result',{}).get('list'):
                return float(r['result']['list'][0]['lastPrice'])
        except: pass
    for url in [f"https://data-api.binance.vision/api/v3/ticker/price?symbol={sym}", f"https://api.binance.com/api/v3/ticker/price?symbol={sym}"]:
        try:
            r = requests.get(url, headers=headers, timeout=5).json()
            if 'price' in r: return float(r['price'])
        except: pass
    return None

app = Flask(__name__)
@app.route('/')
def home(): return "Bot aktif"
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True, silent=True) or {}
        coin = str(data.get('coin','')).upper() or "TV ALARM"
        fiyat = data.get('fiyat') or data.get('price') or ""
        mesaj = data.get('mesaj') or str(data)
        tg(f"📈 *{coin}* {mesaj} {fiyat}")
        return "OK", 200
    except: return "OK", 200

def run_web(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
def keep_alive():
    while True:
        try: requests.get(RENDER_URL, timeout=10)
        except: pass
        time.sleep(240)

threading.Thread(target=run_web, daemon=True).start()
threading.Thread(target=keep_alive, daemon=True).start()

if TOKEN and CHAT_ID: tg("✅ Bot aktif - toleranssiz")
offset = 0

while True:
    try:
        r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={offset}&timeout=10", timeout=15).json()
        for upd in r.get('result', []):
            offset = upd['update_id'] + 1
            raw = upd.get('message', {}).get('text', '').strip()
            if not raw: continue
            up = raw.upper()
            if up == "LISTE":
                msj = "\n".join([f"{k}: {a['fiyat']} {a.get('yon','')}" for k,v in manuel_alarm.items() for a in v]) or "Bos"
                tg(f"📋 {msj}")
            elif up.startswith("SIL"):
                p = up.split()
                if len(p) > 1:
                    c = p[1] if "USDT" in p[1] else p[1]+"USDT"
                    manuel_alarm.pop(c, None); son_fiyat.pop(c, None)
                else:
                    manuel_alarm = {}; son_fiyat = {}
                kaydet(manuel_alarm); tg("🗑 Silindi")
            else:
                parca = raw.split()
                if len(parca) >= 2:
                    coin = parca[0].upper()
                    if "USDT" not in coin: coin += "USDT"
                    try: f = float(parca[1].replace(",", "."))
                    except: continue
                    notu = " ".join(parca[2:]).upper() if len(parca) > 2 else ""
                    cur = fiyat_al(coin)
                    if cur is None:
                        yon = "yaklasik"
                    elif abs(f - cur) / cur < 0.0001:
                        yon = "yaklasik"
                    elif f > cur:
                        yon = "yukari"
                    else:
                        yon = "asagi"
                    if coin not in manuel_alarm: manuel_alarm[coin]=[]
                    if any(abs(a['fiyat']-f) < 1e-9 for a in manuel_alarm[coin]): continue
                    manuel_alarm[coin].append({"fiyat": f, "not": notu, "yon": yon})
                    if cur: son_fiyat[coin] = cur
                    kaydet(manuel_alarm)
                    tg(f"✅ {coin} {f} {notu} ({yon}) eklendi - Anlik: ${cur}")
    except: pass

    for coin, alarmlar in list(manuel_alarm.items()):
        pf = fiyat_al(coin)
        if not pf: continue
        last = son_fiyat.get(coin)
        son_fiyat[coin] = pf
        if last is None: continue

        for a in alarmlar[:]:
            sev = a['fiyat']; yon = a.get('yon','yaklasik'); tetik=False
            if yon == "yukari" and last < sev <= pf: tetik=True
            elif yon == "asagi" and last > sev >= pf: tetik=True
            elif yon == "yaklasik" and ((last < sev <= pf) or (last > sev >= pf)): tetik=True

            if tetik:
                for i in range(3):
                    tg(f"🔔🔔🔔 *{coin} {a['not']} {sev} GELDI!* {i+1}/3\nAnlik: ${pf}")
                    time.sleep(0.7)
                manuel_alarm[coin].remove(a)
                if not manuel_alarm[coin]:
                    del manuel_alarm[coin]; son_fiyat.pop(coin,None)
                kaydet(manuel_alarm)
    time.sleep(2)
