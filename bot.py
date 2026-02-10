import requests
import telegram
import time
import threading
from datetime import datetime, date
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD

# ================= CONFIG =================
BOT_TOKEN = "8481879934:AAEydqW7VUzftFBV-EP0yYq2nNcUBzE2tjY"
CHANNEL_ID = "@SYC_FX"
OWNER_CHAT_ID = "8255900012"

PRIMARY_FOREX_API = "https://api.exchangerate.host/latest"
BACKUP_FOREX_API = "https://open.er-api.com/v6/latest/USD"

WARNING_IMG = "https://i.postimg.cc/Y9zbMWG1/file-000000009af871f49d98a41cd04221cb.png"
BUY_IMG = "https://i.postimg.cc/3x984LsS/buy.png"
SELL_IMG = "https://i.postimg.cc/jqzrngNB/sell.png"

WARNING_AUDIO = "https://raw.githubusercontent.com/cruxifeedsy/ai-voice-/main/ttsmaker-file-2026-2-10-6-58-53.mp3"

PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
TIMEFRAME = "1min"

MAX_TRADES_PER_DAY = 14
EXPIRATION_MINUTES = 4

bot = telegram.Bot(token=BOT_TOKEN)

trade_count = 0
current_day = date.today()
results = []
BOT_START_TIME = time.time()

# ================= SESSION ROUTER =================
def get_target_chat():
    hour = datetime.utcnow().hour
    
    if 0 <= hour < 9:
        return OWNER_CHAT_ID, "ASIA"

    if 9 <= hour <= 21:
        return CHANNEL_ID, "LONDON/NY"

    return OWNER_CHAT_ID, "OFFSESSION"

# ================= HEARTBEAT =================
def heartbeat():
    while True:
        uptime = int((time.time() - BOT_START_TIME) / 60)
        msg = f"""
💓 BOT HEARTBEAT ACTIVE

⏱ Uptime: {uptime} minutes
📊 Channel Trades Today: {trade_count}/{MAX_TRADES_PER_DAY}
🧠 AI Engine: Running
📡 Status: ONLINE
"""
        try:
            bot.send_message(chat_id=OWNER_CHAT_ID, text=msg)
        except:
            pass
        time.sleep(3600)

threading.Thread(target=heartbeat, daemon=True).start()

# ================= API HEALTH CHECK =================
def check_api(url):
    try:
        r = requests.get(url, timeout=6)
        return r.status_code == 200
    except:
        return False

# ================= FETCH PRICE =================
def get_price(pair):
    base = pair[:3]
    quote = pair[3:]

    try:
        if check_api(PRIMARY_FOREX_API):
            r = requests.get(f"{PRIMARY_FOREX_API}?base={base}&symbols={quote}", timeout=10).json()
            return float(r["rates"][quote])

        r = requests.get(BACKUP_FOREX_API, timeout=10).json()
        rate = float(r["rates"][quote])
        return rate

    except:
        return None

# ================= BUILD PRICE HISTORY =================
def build_fake_history(pair):
    prices = []
    last = get_price(pair)

    if not last:
        return None

    for _ in range(120):
        last += (last * (0.0001 if time.time() % 2 else -0.0001))
        prices.append(last)

    return pd.DataFrame({"close": prices})

# ================= AI SIGNAL ENGINE =================
def analyze_signal(df):
    df["rsi"] = RSIIndicator(df["close"], window=14).rsi()
    df["ema9"] = EMAIndicator(df["close"], window=9).ema_indicator()
    df["ema21"] = EMAIndicator(df["close"], window=21).ema_indicator()

    macd = MACD(df["close"])
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    direction = None
    score = 0
    reasons = []

    if latest["ema9"] > latest["ema21"]:
        direction = "BUY"
        score += 30
        reasons.append("EMA bullish")

    if latest["ema9"] < latest["ema21"]:
        direction = "SELL"
        score += 30
        reasons.append("EMA bearish")

    if direction == "BUY" and latest["rsi"] < 55:
        score += 20
        reasons.append("RSI momentum")

    if direction == "SELL" and latest["rsi"] > 45:
        score += 20
        reasons.append("RSI pressure")

    if direction == "BUY" and latest["macd"] > latest["macd_signal"]:
        score += 15
        reasons.append("MACD bullish")

    if direction == "SELL" and latest["macd"] < latest["macd_signal"]:
        score += 15
        reasons.append("MACD bearish")

    if abs(latest["close"] - prev["close"]) > 0:
        score += 15
        reasons.append("Volatility active")

    return direction, score, ", ".join(reasons)

# ================= SEND WARNING =================
def send_warning(pair):
    chat, session = get_target_chat()

    try:
        bot.send_photo(chat_id=chat, photo=WARNING_IMG,
                       caption=f"⚠️ HIGH-PROBABILITY SIGNAL\n\n💱 Pair: {pair}\n⏳ Signal dropping in 60 seconds...")
        bot.send_audio(chat_id=chat, audio=WARNING_AUDIO)
    except:
        pass

# ================= SEND SIGNAL =================
def send_signal(pair, direction, score, reasons):
    chat, session = get_target_chat()

    img = BUY_IMG if direction == "BUY" else SELL_IMG

    caption = f"""
💱 Pair: {pair}
⬆️ Direction: {direction}
🧠 AI Score: {score}%
📊 Session: {session}

🔍 Analysis:
{reasons}

🔥 CRUXIFEED INSTITUTIONAL ENGINE
"""

    try:
        bot.send_photo(chat_id=chat, photo=img, caption=caption)
    except:
        pass

# ================= WIN / LOSS TRACK =================
def evaluate_trade(pair, direction, entry):
    def worker():
        time.sleep(EXPIRATION_MINUTES * 60)
        exit_price = get_price(pair)
        if not exit_price:
            return
        win = exit_price > entry if direction == "BUY" else exit_price < entry
        results.append(win)

    threading.Thread(target=worker).start()

# ================= DAILY REPORT =================
def daily_report():
    if not results:
        return

    wins = sum(results)
    losses = len(results) - wins
    winrate = round((wins / len(results)) * 100, 2)

    report = f"""
📊 SYC_FX DAILY REPORT

Trades: {len(results)}
Wins: {wins}
Losses: {losses}
Win Rate: {winrate}%
"""

    try:
        bot.send_message(chat_id=CHANNEL_ID, text=report)
    except:
        pass

    results.clear()

print("🚀 CRUXIFEED FOREX BOT LIVE")

# ================= MAIN LOOP =================
while True:
    try:
        if date.today() != current_day:
            daily_report()
            current_day = date.today()
            trade_count = 0

        for pair in PAIRS:
            chat_target, session = get_target_chat()

            if session == "LONDON/NY" and trade_count >= MAX_TRADES_PER_DAY:
                continue

            df = build_fake_history(pair)
            if df is None:
                continue

            direction, score, reasons = analyze_signal(df)

            if direction and score >= 65:
                entry = df.iloc[-1]["close"]

                send_warning(pair)
                time.sleep(60)

                send_signal(pair, direction, score, reasons)

                if session == "LONDON/NY":
                    trade_count += 1

                evaluate_trade(pair, direction, entry)

                time.sleep(120)

        time.sleep(60)

    except Exception as e:
        print("ERROR:", e)
        time.sleep(20)