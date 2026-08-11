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

def fiyat_al_kaynakli(sym):
    headers = {"User-Agent": "Mozilla/5.0"}
    # 1. Bybit Linear = Vadeli (senin islem yaptigin yer)
    try:
        r = requests.get(f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={sym}", headers=headers, timeout=6).json()
        if r.get('retCode') == 0 and r.get('result', {}).get('list'):
            return float(r['result']['list'][0]['lastPrice']), "Bybit Vadeli"
    except:
        pass
    # 2. Bybit Spot
    try:
        r = requests.get(f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={sym}", headers=headers, timeout=6).json()
        if r.get('retCode') == 0 and r.get('result', {}).get('list'):
            return float(r['result']['list'][0]['lastPrice']), "Bybit Spot"
    except:
        pass
    # 3. Binance yedekler
    try:
        r = requests.get(f"https://data-api.binance.vision/api/v3/ticker/price?symbol={sym}", headers=headers, timeout=5).json()
        if 'price' in r:
            return float(r['price']), "Binance Yedek"
    except:
        pass
    try:
        r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={sym}", headers=headers, timeout=5).json()
        if 'price' in r:
            return float(r['price']), "Binance Yedek2"
    except:
        pass
    return None, None

def fiyat_al(sym):
    f, _ = fiyat_al_kaynakli(sym)
    return f

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot 7/24 aktif - Bybit Vadeli fiyatli"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True, silent=True) or {}
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

print("Bot basladi - BYBIT VADELI + webhook aktif")
if TOKEN and CHAT_ID:
    tg("✅ Bot 7/24 aktif - Bybit Vadeli fiyatlari ile calisiyor")

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
                        cur, kaynak = fiyat_al_kaynakli(coin)
                        if "YUKARI" in notu or "USTU" in notu or "ÜSTÜ" in notu or "YUKAR" in notu:
                            yon = "yukari"
                        elif "ASAGI" in notu or "AŞAĞI" in notu or "ALTI" in notu or "ASAG" in notu:
                            yon = "asagi"
                        else:
                            yon = "yaklasik"
                            if cur is not None:
                                yon = "yukari" if fiyat > cur else "asagi"
                        if coin not in manuel_alarm:
                            manuel_alarm[coin] = []
                        manuel_alarm[coin].append({"fiyat": fiyat, "not": notu, "yon": yon})
                        kaydet(manuel_alarm)
                        if cur:
                            tg(f"✅ {coin} {fiyat} {notu} ({yon}) eklendi - Anlik {kaynak}: ${cur}")
                        else:
                            tg(f"✅ {coin} {fiyat} {notu} eklendi - Fiyat alinamadi ama alarm aktif")
                    except Exception as e:
                        print(e)
    except Exception as e:
        print("getUpdates hata:", e)

    for coin, alarmlar in list(manuel_alarm.items()):
        f, kaynak = fiyat_al_kaynakli(coin)
        if not f:
            continue
        for a in alarmlar[:]:
            sev = a['fiyat']
            yon = a.get('yon', 'yaklasik')
            tetikle = False
            if yon == "yukari":
                if f >= sev:
                    tetikle = True
            elif yon == "asagi":
                if f <= sev:
                    tetikle = True
            else:
                if abs(f - sev) / sev < 0.0001:
                    tetikle = True
            if tetikle:
                for i in range(3):
                    tg(f"🔔🔔🔔 *{coin} {a['not']} {sev} GELDI!* {i+1}/3\nAnlik {kaynak}: ${f}")
                    time.sleep(1)
                manuel_alarm[coin].remove(a)
                if not manuel_alarm[coin]:
                    del manuel_alarm[coin]
                kaydet(manuel_alarm)
    time.sleep(3)
