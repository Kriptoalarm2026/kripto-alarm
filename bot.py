import requests, time, threading, json, os
from flask import Flask
import telebot

TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise Exception("BOT_TOKEN env yok!")
bot = telebot.TeleBot(TOKEN)

ALARMS_FILE = "alarms.json"
alarms = []
file_lock = threading.Lock()

app = Flask(__name__)
@app.route('/')
def home():
    return "Bot Aktif - Bybit+Bitget", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def get_price_bybit(symbol):
    symbol = symbol.upper().replace(".P","").replace("/","").strip()
    if not symbol.endswith("USDT"):
        symbol += "USDT"

    # 1. Bybit (Spot -> Linear -> Inverse)
    for cat in ["spot", "linear", "inverse"]:
        try:
            url = f"https://api.bybit.com/v5/market/tickers?category={cat}&symbol={symbol}"
            r = requests.get(url, timeout=5).json()
            lst = r.get("result", {}).get("list", [])
            if lst and lst[0].get("lastPrice"):
                return float(lst[0]["lastPrice"])
        except:
            continue

    # 2. Bitget Fallback (Spot V2 API)
    bitget_symbols = [symbol, f"{symbol[:-4]}_USDT"]
    for bg_sym in bitget_symbols:
        try:
            url = f"https://api.bitget.com/api/v2/spot/market/tickers?symbol={bg_sym}"
            r = requests.get(url, timeout=5).json()
            data = r.get("data", [])
            if data and data[0].get("lastPr"):
                return float(data[0]["lastPr"])
        except:
            continue

    print(f"Fiyat bulunamadı: {symbol}")
    return None

def load_alarms():
    global alarms
    with file_lock:
        if os.path.exists(ALARMS_FILE):
            try:
                with open(ALARMS_FILE, 'r') as f:
                    alarms = json.load(f)
            except:
                alarms = []

def save_alarms():
    with file_lock:
        with open(ALARMS_FILE, 'w') as f:
            json.dump(alarms, f)

@bot.message_handler(func=lambda m: True)
def handle_all(message):
    global alarms
    text = message.text.lower().strip()

    if text.startswith("sil"):
        parts = text.split()
        with file_lock:
            if len(parts) == 1:
                alarms = []
            else:
                coin = parts[1].upper()
                alarms = [a for a in alarms if not a['symbol'].startswith(coin)]
        save_alarms()
        bot.reply_to(message, "🗑 Silindi")
        return

    if text.startswith("liste"):
        with file_lock:
            current_list = list(alarms)
        if not current_list:
            bot.reply_to(message, "Liste boş")
        else:
            msg = "\n".join([f"{a['symbol']} {a['target']} ({a['yon']})" for a in current_list])
            bot.reply_to(message, msg)
        return

    try:
        parts = text.split()
        if len(parts)!= 2:
            return
        coin, target = parts[0], float(parts[1])
        symbol = coin.upper() + "USDT" if not coin.upper().endswith("USDT") else coin.upper()

        price = get_price_bybit(symbol)
        if price is None:
            bot.reply_to(message, f"❌ {symbol} Bybit/Bitget'te bulunamadı.")
            return

        yon = "asagi" if price > target else "yukari"
        new_alarm = {"symbol": symbol, "target": target, "yon": yon, "chat_id": message.chat.id}

        with file_lock:
            alarms.append(new_alarm)
        save_alarms()
        bot.reply_to(message, f"✅ {symbol} {target} ({yon}) eklendi - Anlik: ${price}")
    except Exception as e:
        print(f"handle hata: {e}")

def check_alarms_loop():
    global alarms
    while True:
        time.sleep(15)
        with file_lock:
            current_alarms = list(alarms)

        if not current_alarms:
            continue

        unique_symbols = list(set(a['symbol'] for a in current_alarms))
        prices = {sym: get_price_bybit(sym) for sym in unique_symbols}

        for alarm in current_alarms:
            price = prices.get(alarm['symbol'])
            if price is None:
                continue

            tetiklendi = (alarm['yon'] == 'asagi' and price <= alarm['target']) or \
                         (alarm['yon'] == 'yukari' and price >= alarm['target'])

            if tetiklendi:
                try:
                    bot.send_message(alarm['chat_id'], f"🔔🔔🔔 {alarm['symbol']} {alarm['target']} GELDI! Anlik: ${price}")
                    with file_lock:
                        if alarm in alarms:
                            alarms.remove(alarm)
                    save_alarms()
                except Exception as e:
                    print(f"alarm hata: {e}")

if __name__ == "__main__":
    load_alarms()
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=check_alarms_loop, daemon=True).start()
    print("Bot baslatiliyor...")
    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            print(f"Polling çöktü, 5sn sonra restart: {e}")
            time.sleep(5)
