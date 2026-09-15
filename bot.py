import os, json, requests, time, threading
from flask import Flask, request

TOKEN = os.getenv("TOKEN") or os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
DOSYA = "alarmlar.json"

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
        data={"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "Markdown"}, timeout=10)
    except:
        pass

def fiyat_al_kaynakli(sym):
    headers = {"User-Agent": "Mozilla/5.0"}
    sym = sym.upper()
    # Bybit'te SOXL, KORU gibi CFD'ler USDT'siz geliyor, o yüzden ikisini de dene
    for s in [sym, sym.replace("USDT","")]:
        try:
            r = requests.get(f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={s}", headers=headers, timeout=6).json()
            if r.get('retCode') == 0 and r.get('result', {}).get('list'):
                return float(r['result']['list'][0]['lastPrice']), "Bybit Vadeli"
        except:
            pass
        try:
            r = requests.get(f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={s}", headers=headers, timeout=6).json()
            if r.get('retCode') == 0 and r.get('result', {}).get('list'):
                return float(r['result']['list'][0]['lastPrice']), "Bybit Spot"
        except:
            pass
    return None, None

def fiyat_al(sym):
    f, _ = fiyat_al_kaynakli(sym)
    return f

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot 7/24 aktif - Bybit"

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
        return "ERR", 200

def run_web():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

def keep_alive():
    url = os.getenv("RENDER_EXTERNAL_URL")
    while True:
        time.sleep(600)
        if url:
            try:
                requests.get(url, timeout=10)
            except:
                pass

threading.Thread(target=run_web, daemon=True).start()
threading.Thread(target=keep_alive, daemon=True).start()

print("Bot basladi - BYBIT")
if TOKEN and CHAT_ID:
    tg("✅ Bot 7/24 aktif - Bybit fiyatlari ile calisiyor")

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
                lines = []
                for k,v in manuel_alarm.items():
                    for a in v:
                        lines.append(f"{k}: {a['fiyat']} {a.get('not','')} ({a.get('yon','')})")
                tg("📋 " + "\n".join(lines) if lines else "Bos")
            elif up.startswith("SIL"):
                p = up.split()
                if len(p) > 1:
                    c = p[1].upper()
                    manuel_alarm.pop(c, None)
                    manuel_alarm.pop(c[:-4] if c.endswith("USDT") else c+"USDT", None)
                else:
                    manuel_alarm = {}
                kaydet(manuel_alarm)
                tg("🗑️ Silindi")
            else:
                parca = raw.split()
                if len(parca) >= 2:
                    coin_raw = parca[0].upper()
                    coin = coin_raw if "USDT" in coin_raw else coin_raw + "USDT"
                    try:
                        fiyat = float(parca[1].replace(",", "."))
                    except:
                        continue
                    notu = " ".join(parca[2:]).upper() if len(parca) > 2 else ""
                    cur, kaynak = fiyat_al_kaynakli(coin)
                    if cur is None:
                        cur, kaynak = fiyat_al_kaynakli(coin.replace("USDT",""))
                    if "YUKARI" in notu or "USTU" in notu or "ÜSTÜ" in notu:
                        yon = "yukari"
                    elif "ASAGI" in notu or "AŞAĞI" in notu or "ALTI" in notu:
                        yon = "asagi"
                    else:
                        yon = "yukari" if cur and fiyat > cur else "asagi" if cur else "yaklasik"
                    if coin not in manuel_alarm:
                        manuel_alarm[coin] = []
                    manuel_alarm[coin].append({"fiyat": fiyat, "not": notu, "yon": yon})
                    kaydet(manuel_alarm)
                    if cur:
                        tg(f"✅ {coin} {fiyat} {notu} ({yon}) eklendi - Anlik {kaynak}: ${cur}")
                    else:
                        tg(f"✅ {coin} {fiyat} {notu} ({yon}) eklendi")
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
            if yon == "yukari" and f >= sev:
                tetikle = True
            elif yon == "asagi" and f <= sev:
                tetikle = True
            elif yon == "yaklasik" and abs(f - sev) / sev < 0.0001:
                tetikle = True
            if tetikle:
                for i in range(3):
                    tg(f"🔔🔔🔔 *{coin} {a.get('not','')} {sev} GELDI!* {i+1}/3\nAnlik {kaynak}: ${f}")
                    time.sleep(1)
                manuel_alarm[coin].remove(a)
                if not manuel_alarm[coin]:
                    del manuel_alarm[coin]
                kaydet(manuel_alarm)
    time.sleep(3)
