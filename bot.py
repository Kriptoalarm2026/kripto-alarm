import os, json, requests, time, threading
from flask import Flask, request

TOKEN = os.getenv("TOKEN") or os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
DOSYA = "alarmlar.json"
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL") or "https://kripto-alarm-0rqu.onrender.com"

def yukle():
    try:
        with open(DOSYA, "r") as f:
            return json.load(f)
    except:
        return {}

def kaydet(d):
    try:
        with open(DOSYA, "w") as f:
            json.dump(d, f)
    except:
        pass

manuel_alarm = yukle()

def tg(mesaj):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": mesaj, "parse_mode":"Markdown", "disable_notification": False}, timeout=10)
    except:
        pass

def fiyat_al(sym):
    try:
        r = requests.get(f"https://data-api.binance.vision/api/v3/ticker/price?symbol={sym}", timeout=5).json()
        return float(r['price'])
    except:
        return None

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot 7/24 aktif - Render Free"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True, silent=True) or {}
        # TradingView den gelen JSON: {"coin":"BTCUSDT", "fiyat": 64045, "mesaj":"SMA KIRILDI"}
        if not data:
            data = {"mesaj": request.data.decode('utf-8', errors='ignore')}
        
        coin = str(data.get('coin','')).upper() or "TV ALARM"
        fiyat = data.get('fiyat') or data.get('price') or ""
        mesaj = data.get('mesaj') or data.get('message') or data.get('text') or str(data)
        
        if fiyat:
            tg(f"📈 *{coin}* {mesaj}\nSeviye: {fiyat}")
        else:
            tg(f"📈 *{coin}*\n{mesaj}")
            
        return "OK", 200
    except Exception as e:
        print("webhook hata", e)
        return "ERROR", 200

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    while True:
        try:
            requests.get(RENDER_URL, timeout=10)
        except:
            pass
        time.sleep(240)

threading.Thread(target=run_web, daemon=True).start()
threading.Thread(target=keep_alive, daemon=True).start()

print("Bot basladi - keepalive + webhook aktif")
if TOKEN and CHAT_ID:
    tg("✅ Bot 7/24 aktif - TV webhook: /webhook hazir")

offset = 0
while True:
    try:
        r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={offset}&timeout=10", timeout=15).json()
        for upd in r.get('result', []):
            offset = upd['update_id'] + 1
            raw = upd.get('message', {}).get('text', '').strip()
            if not raw:
                continue
            up = raw.upper()
            if up == "LISTE":
                msj = "\n".join([f"{k}: {v}" for k,v in manuel_alarm.items()]) or "Bos"
                tg(f"📋 {msj}")
            elif up.startswith("SIL"):
                p = up.split()
                if len(p) > 1:
                    c = p[1] if "USDT" in p[1] else p[1]+"USDT"
                    manuel_alarm.pop(c, None)
                else:
                    manuel_alarm = {}
                kaydet(manuel_alarm)
                tg("🗑️ Silindi")
            else:
                parca = raw.split()
                if len(parca) >= 2:
                    try:
                        coin = parca[0].upper()
                        if "USDT" not in coin:
                            coin += "USDT"
                        fiyat = float(parca[1].replace(",", "."))
                        notu = " ".join(parca[2:]).upper() if len(parca) > 2 else ""
                        if coin not in manuel_alarm:
                            manuel_alarm[coin] = []
                        manuel_alarm[coin].append({"fiyat": fiyat, "not": notu})
                        kaydet(manuel_alarm)
                        tg(f"✅ {coin} {fiyat} {notu} eklendi")
                    except:
                        pass
    except:
        pass
    for coin, alarmlar in list(manuel_alarm.items()):
        f = fiyat_al(coin)
        if not f:
            continue
        for a in alarmlar[:]:
            sev = a['fiyat']
            if abs(f - sev) / sev < 0.001:
                for i in range(3):
                    tg(f"🔔🔔🔔 *{coin} {a['not']} {sev} GELDI!* {i+1}/3\nAnlik: ${f}")
                    time.sleep(1)
                manuel_alarm[coin].remove(a)
                if not manuel_alarm[coin]:
                    del manuel_alarm[coin]
                kaydet(manuel_alarm)
    time.sleep(10)
