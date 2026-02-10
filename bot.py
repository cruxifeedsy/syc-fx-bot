 import asyncio
import requests
import time
from datetime import datetime, date
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD
from telegram import Bot
from telegram.ext import ApplicationBuilder

# ===== CONFIG =====
BOT_TOKEN = "8481879934:AAHKN5KoKzv0b5OwG9Ksut0zyKrp7Yu8Uhw"
CHANNEL_ID = "@SYC_FX"
OWNER_CHAT_ID = "8255900012"

PRIMARY_FOREX_API = "https://api.exchangerate.host/latest"
BACKUP_FOREX_API = "https://open.er-api.com/v6/latest/USD"

WARNING_IMG = "https://i.postimg.cc/Y9zbMWG1/file-000000009af871f49d98a41cd04221cb.png"
BUY_IMG = "https://i.postimg.cc/3x984LsS/buy.png"
SELL_IMG = "https://i.postimg.cc/jqzrngNB/sell.png"

AUDIO_WARNING = "https://raw.github.com/cruxifeedsy/ai-voice-/main/ttsmaker-file-2026-2-10-6-58-53.mp3"

MAX_TRADES_PER_DAY = 14
PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]

TIMEFRAME = "1min"
EXPIRATION_MINUTES = 4

trade_count = 0
results = []
current_day = date.today()
BOT_START_TIME = time.time()

bot = Bot(token=BOT_TOKEN)

# ===== SESSION ROUTER =====
def get_target_chat():
    hour = datetime.utcnow().hour

    if 0 <= hour < 9:
        return OWNER_CHAT_ID, "ASIA"

    if 9 <= hour <= 21:
        return CHANNEL_ID, "LONDON/NY"

    return OWNER_CHAT_ID, "OFFSESSION"

# ===== API HEALTH CHECK =====
def api_health_check(url):
    try:
        r = requests.get(url, timeout=5)
        return r.status_code == 200
    except:
        return False

# ===== MARKET DATA FETCH =====
def get_market_data(pair):
    try:
        base = pair[:3]
        quote = pair[3:]

        url = f"https://api.exchangerate.host/timeseries?base={base}&symbols={quote}&start_date=2024-01-01&end_date=2024-12-31"
        r = requests.get(url, timeout=10).json()

        if "rates" not in r:
            return None

        prices = list(r["rates"].values())[-200:]
        closes = [list(p.values())[0] for p in prices]

        df = pd.DataFrame({"close": closes})
        return df

    except:
        return None

# ===== AI ENGINE =====
def analyze_signal(df):
    if df is None or len(df) < 30:
        return None, 0, None

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

    if latest["ema9"] > latest["ema21"] and prev["ema9"] <= prev["ema21"]:
        direction = "BUY"
        score += 35
        reasons.append("EMA bullish cross")

    if latest["ema9"] < latest["ema21"] and prev["ema9"] >= prev["ema21"]:
        direction = "SELL"
        score += 35
        reasons.append("EMA bearish cross")

    if not direction:
        return None, 0, None

    if direction == "BUY" and latest["rsi"] < 50:
        score += 20
        reasons.append("RSI oversold")

    if direction == "SELL" and latest["rsi"] > 50:
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
        score += 10
        reasons.append("Momentum rising")

    if direction == "SELL" and momentum < 0:
        score += 10
        reasons.append("Momentum falling")

    return direction, score, ", ".join(reasons)

# ===== HEARTBEAT =====
async def heartbeat():
    while True:
        uptime = int((time.time() - BOT_START_TIME) / 60)
        msg = f"""
💓 BOT HEARTBEAT ACTIVE
⏱ Uptime: {uptime} minutes
📊 Trades Today: {trade_count}/{MAX_TRADES_PER_DAY}
📡 Status: ONLINE
"""
        await bot.send_message(chat_id=OWNER_CHAT_ID, text=msg)
        await asyncio.sleep(3600)

# ===== WARNING =====
async def send_warning(pair):
    await bot.send_audio(chat_id=OWNER_CHAT_ID, audio=AUDIO_WARNING)
    await bot.send_photo(
        chat_id=OWNER_CHAT_ID,
        photo=WARNING_IMG,
        caption=f"⚠️ HIGH-PROBABILITY SIGNAL\n\n💱 Pair: {pair}\n⏳ Sending in 60 seconds..."
    )

# ===== SIGNAL SEND =====
async def send_signal(pair, direction, score, reasons):
    global trade_count

    chat_target, session_name = get_target_chat()

    if session_name == "LONDON/NY" and trade_count >= MAX_TRADES_PER_DAY:
        return

    img = BUY_IMG if direction == "BUY" else SELL_IMG

    caption = f"""
💱 Pair: {pair}
⬆️ Direction: {direction}
🧠 AI Score: {score}%
📊 Session: {session_name}

🔍 Reason:
{reasons}

🔥 Cruxifeed Institutional Engine
"""

    await bot.send_photo(chat_id=chat_target, photo=img, caption=caption)

    if session_name == "LONDON/NY":
        trade_count += 1

# ===== MAIN LOOP =====
async def main_loop():
    global trade_count, current_day

    asyncio.create_task(heartbeat())

    while True:
        try:
            if date.today() != current_day:
                trade_count = 0
                current_day = date.today()

            for pair in PAIRS:
                df = get_market_data(pair)
                direction, score, reasons = analyze_signal(df)

                if direction and score >= 70:
                    await send_warning(pair)
                    await asyncio.sleep(60)
                    await send_signal(pair, direction, score, reasons)

            await asyncio.sleep(60)

        except Exception as e:
            print("ERROR:", e)
            await asyncio.sleep(30)

# ===== START BOT =====
if __name__ == "__main__":
    print("🚀 CRUXIFEED ELITE BOT LIVE")
    asyncio.run(main_loop())