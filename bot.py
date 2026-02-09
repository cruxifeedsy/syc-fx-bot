import requests
import telegram
import time
from datetime import datetime, date
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD
import threading

# ===== YOUR KEYS =====
BOT_TOKEN = "8230940323:AAEOfrX_h8XymGWLWmv5ywCGVrWViBiK864"
CHANNEL_ID = "@SYC_FX"      # SIGNALS GO HERE
OWNER_CHAT_ID = "8255900012"  # HEARTBEAT GOES TO YOU
TWELVE_API_KEY = "454cf9eb0d8d4fa7a8b033b256eeb6ab"

# ===== IMAGES =====
WARNING_IMG = "https://i.postimg.cc/Y9zbMWG1/file-000000009af871f49d98a41cd04221cb.png"
BUY_IMG = "https://i.postimg.cc/3x984LsS/buy.png"
SELL_IMG = "https://i.postimg.cc/jqzrngNB/sell.png"

bot = telegram.Bot(token=BOT_TOKEN)

# ===== SETTINGS =====
MAX_TRADES_PER_DAY = 14
PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
TIMEFRAME = "1min"
EXPIRATION_MINUTES = 4

trade_count = 0
current_day = date.today()
results = []

BOT_START_TIME = time.time()

# ===== HEARTBEAT SYSTEM (PRIVATE CHAT) =====
def heartbeat():
    while True:
        try:
            uptime = int((time.time() - BOT_START_TIME) / 60)
            msg = f"""
💓 BOT HEARTBEAT ACTIVE

⏱ Uptime: {uptime} minutes
📊 Trades Today: {trade_count}/{MAX_TRADES_PER_DAY}
🧠 AI Engine: Running
📡 Status: ONLINE
"""
            bot.send_message(chat_id=OWNER_CHAT_ID, text=msg)
            time.sleep(600)
        except:
            time.sleep(60)

threading.Thread(target=heartbeat, daemon=True).start()

# ===== SESSION FILTER (LONDON + NY) =====
def london_ny_session():
    hour = datetime.utcnow().hour
    return 12 <= hour <= 17

# ===== FETCH MARKET DATA =====
def get_market_data(pair):
    url = f"https://api.twelvedata.com/time_series?symbol={pair}&interval={TIMEFRAME}&outputsize=200&apikey={TWELVE_API_KEY}"
    try:
        r = requests.get(url, timeout=10).json()
        if "values" not in r:
            return None
        df = pd.DataFrame(r["values"])
        df["close"] = df["close"].astype(float)
        return df.iloc[::-1]
    except:
        return None

# ===== AI SCORING ENGINE =====
def analyze_signal(df):
    df["rsi"] = RSIIndicator(df["close"], window=14).rsi()
    df["ema9"] = EMAIndicator(df["close"], window=9).ema_indicator()
    df["ema21"] = EMAIndicator(df["close"], window=21).ema_indicator()

    macd = MACD(df["close"])
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    score = 0
    direction = None
    reasons = []

    trend_strength = abs(latest["ema9"] - latest["ema21"])
    if trend_strength < 0.00005:
        return None, 0, None

    if latest["ema9"] > latest["ema21"] and prev["ema9"] <= prev["ema21"]:
        direction = "BUY"
        score += 30
        reasons.append("EMA bullish cross")

    if latest["ema9"] < latest["ema21"] and prev["ema9"] >= prev["ema21"]:
        direction = "SELL"
        score += 30
        reasons.append("EMA bearish cross")

    if not direction:
        return None, 0, None

    if direction == "BUY" and latest["rsi"] < 45:
        score += 20
        reasons.append("RSI oversold")

    if direction == "SELL" and latest["rsi"] > 55:
        score += 20
        reasons.append("RSI overbought")

    if direction == "BUY" and latest["macd"] > latest["macd_signal"]:
        score += 15
        reasons.append("MACD bullish")

    if direction == "SELL" and latest["macd"] < latest["macd_signal"]:
        score += 15
        reasons.append("MACD bearish")

    momentum = latest["close"] - prev["close"]

    if direction == "BUY" and momentum > 0:
        score += 15
        reasons.append("Momentum rising")

    if direction == "SELL" and momentum < 0:
        score += 15
        reasons.append("Momentum falling")

    return direction, score, ", ".join(reasons)

# ===== TELEGRAM SIGNALS =====
def send_warning(pair):
    bot.send_photo(
        chat_id=CHANNEL_ID,
        photo=WARNING_IMG,
        caption=f"⚠️ HIGH-PROBABILITY SIGNAL\n\n💱 Pair: {pair}\n⏳ Sending in 60 seconds..."
    )

def send_signal(pair, direction, score, reasons):
    img = BUY_IMG if direction == "BUY" else SELL_IMG

    caption = f"""
💱 Pair: {pair}
⏱️ Timeframe: 1 Minute
🕒 Expiration: 3–5 Minutes
⬆️ Direction: {direction}

🧠 AI Score: {score}%
🔍 Analysis: {reasons}
📍 Session: London + New York
🔥 Institutional-Grade Filter
"""

    bot.send_photo(chat_id=CHANNEL_ID, photo=img, caption=caption)

# ===== WIN / LOSS TRACKER =====
def evaluate_trade(pair, direction, entry_price):
    def worker():
        time.sleep(EXPIRATION_MINUTES * 60)
        df = get_market_data(pair)
        if df is None:
            return

        exit_price = df.iloc[-1]["close"]
        win = exit_price > entry_price if direction == "BUY" else exit_price < entry_price
        results.append(win)

    threading.Thread(target=worker).start()

# ===== DAILY REPORT =====
def daily_report():
    if not results:
        return

    wins = sum(results)
    losses = len(results) - wins
    winrate = round((wins / len(results)) * 100, 2)

    report = f"""
📊 SYC_FX DAILY PERFORMANCE REPORT

Trades: {len(results)}
Wins: {wins}
Losses: {losses}
Win Rate: {winrate}%

Session: London + New York
AI Engine: ACTIVE
"""

    bot.send_message(chat_id=CHANNEL_ID, text=report)
    results.clear()

print("🚀 SYC_FX BOT LIVE...")

# ===== MAIN LOOP =====
while True:
    try:
        if date.today() != current_day:
            daily_report()
            current_day = date.today()
            trade_count = 0

        if trade_count >= MAX_TRADES_PER_DAY:
            time.sleep(600)
            continue

        if not london_ny_session():
            time.sleep(300)
            continue

        for pair in PAIRS:
            if trade_count >= MAX_TRADES_PER_DAY:
                break

            df = get_market_data(pair)
            if df is None:
                continue

            direction, score, reasons = analyze_signal(df)

            if direction and score >= 80:
                entry_price = df.iloc[-1]["close"]

                send_warning(pair)
                time.sleep(60)

                send_signal(pair, direction, score, reasons)

                trade_count += 1

                evaluate_trade(pair, direction, entry_price)

                time.sleep(120)

        time.sleep(60)

    except Exception as e:
        print("ERROR:", e)
        time.sleep(30)