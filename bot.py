import os, json, requests, time

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
DOSYA = "alarmlar.json"

def yukle():
    try:
        with open(DOSYA, "r") as f:
            return json.load(f)
    except:
        return {}

def kaydet(d):
    with open(DOSYA, "w") as f:
        json.dump(d, f)

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

print("Bot basladi, alarmlar:", manuel_alarm)
tg("✅ Bot 7/24 aktif - PC kapansa da calisir")

offset = 0
while True:
    # Telegram'dan gelen mesajlari dinle
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
                        tg(f"✅ {coin} {fiyat} {notu} eklendi - PC kapali olsa da calacak")
                    except Exception as e:
                        print(e)
                        pass
    except Exception as e:
        print("getUpdates hata:", e)

    # Fiyat kontrol
    for coin, alarmlar in list(manuel_alarm.items()):
        f = fiyat_al(coin)
        if not f:
            continue
        for a in alarmlar[:]:
            sev = a['fiyat']
            if abs(f - sev) / sev < 0.001:  # %0.1 yaklasinca cal
                for i in range(3):
                    tg(f"🔔🔔🔔 *{coin} {a['not']} {sev} GELDI!* {i+1}/3\nAnlik: ${f}")
                    time.sleep(1)
                manuel_alarm[coin].remove(a)
                if not manuel_alarm[coin]:
                    del manuel_alarm[coin]
                kaydet(manuel_alarm)
    time.sleep(10)
