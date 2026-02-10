import asyncio
import requests
import time
import random
from datetime import datetime, date
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD
from telegram import Bot

# ===== CONFIG =====
BOT_TOKEN = "8481879934:AAHKN5KoKzv0b5OwG9Ksut0zyKrp7Yu8Uhw"
CHANNEL_ID = "@SYC_FX"
OWNER_CHAT_ID = "8255900012"

PRIMARY_API = "https://api.exchangerate.host/timeseries"
BACKUP_API = "https://open.er-api.com/v6/latest/USD"

WARNING_IMG = "https://i.postimg.cc/Y9zbMWG1/file-000000009af871f49d98a41cd04221cb.png"
BUY_IMG = "https://i.postimg.cc/3x984LsS/buy.png"
SELL_IMG = "https://i.postimg.cc/jqzrngNB/sell.png"

AUDIO_WARNING = "https://raw.github.com/cruxifeedsy/ai-voice-/main/ttsmaker-file-2026-2-10-6-58-53.mp3"

PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]

MAX_TRADES_PER_DAY = 9
MIN_TRADES_PER_DAY = 6
MARKET_SCAN_SECONDS = 3

trade_count = 0
wins = 0
losses = 0
loss_streak = 0
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

# ===== MARKET DATA =====
def get_market_data(pair):
    base = pair[:3]
    quote = pair[3:]

    try:
        url = f"{PRIMARY_API}?base={base}&symbols={quote}&start_date=2024-01-01&end_date=2024-12-31"
        r = requests.get(url, timeout=10).json()

        if "rates" not in r:
            raise Exception("Primary API failed")

        prices = list(r["rates"].values())[-300:]
        closes = [list(p.values())[0] for p in prices]

        return pd.DataFrame({"close": closes})

    except:
        try:
            r = requests.get(BACKUP_API, timeout=10).json()
            base_price = r["rates"].get(quote)
            if not base_price:
                return None

            closes = [base_price] * 300
            return pd.DataFrame({"close": closes})

        except:
            return None

# ===== ELITE ANALYSIS ENGINE =====
def analyze_signal(df):
    if df is None or len(df) < 80:
        return None, 0, None, None

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

    # Strong trend filter
    trend_strength = abs(latest["ema9"] - latest["ema21"])
    if trend_strength < 0.00006:
        return None, 0, None, None

    # Volatility filter
    volatility = df["close"].pct_change().rolling(10).std().iloc[-1]
    if volatility < 0.00002:
        return None, 0, None, None

    # Direction logic
    if latest["ema9"] > latest["ema21"] and prev["ema9"] <= prev["ema21"]:
        direction = "BUY"
        score += 45
        reasons.append("Strong EMA bullish crossover")

    if latest["ema9"] < latest["ema21"] and prev["ema9"] >= prev["ema21"]:
        direction = "SELL"
        score += 45
        reasons.append("Strong EMA bearish crossover")

    if not direction:
        return None, 0, None, None

    # RSI confirmation
    if direction == "BUY" and latest["rsi"] < 47:
        score += 20
        reasons.append("RSI oversold")

    if direction == "SELL" and latest["rsi"] > 53:
        score += 20
        reasons.append("RSI overbought")

    # MACD confirmation
    if direction == "BUY" and latest["macd"] > latest["macd_signal"]:
        score += 15
        reasons.append("MACD bullish")

    if direction == "SELL" and latest["macd"] < latest["macd_signal"]:
        score += 15
        reasons.append("MACD bearish")

    # Momentum filter
    momentum = latest["close"] - prev["close"]

    if direction == "BUY" and momentum > 0:
        score += 10
        reasons.append("Momentum rising")

    if direction == "SELL" and momentum < 0:
        score += 10
        reasons.append("Momentum falling")

    # Smart expiration logic
    if trend_strength > 0.00015:
        expiration = 2
    elif volatility > 0.00005:
        expiration = 3
    else:
        expiration = 5

    return direction, score, ", ".join(reasons), expiration

# ===== HEARTBEAT =====
async def heartbeat():
    while True:
        uptime = int((time.time() - BOT_START_TIME) / 60)
        msg = f"""
💓 CRUXIFEED HEARTBEAT

⏱ Uptime: {uptime} minutes
📊 Trades Today: {trade_count}/{MAX_TRADES_PER_DAY}
🏆 Wins: {wins}
❌ Losses: {losses}
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
        caption=f"⚠️ HIGH-CONVICTION SIGNAL\n\n💱 Pair: {pair}\n⏳ Sending trade in 60 seconds..."
    )

# ===== SEND SIGNAL =====
async def send_signal(pair, direction, score, reasons, expiration):
    global trade_count

    chat_target, session_name = get_target_chat()

    if session_name == "LONDON/NY" and trade_count >= MAX_TRADES_PER_DAY:
        return

    img = BUY_IMG if direction == "BUY" else SELL_IMG

    caption = f"""
🚨 ELITE TRADE ALERT

💱 Pair: {pair}
📈 Direction: {direction}
🧠 Confidence Score: {score}%

⌛ Expiration: {expiration} MIN

🔍 Signal Logic:
{reasons}

🔥 Cruxifeed LEVEL-3 Engine
"""

    await bot.send_photo(chat_id=chat_target, photo=img, caption=caption)

    if session_name == "LONDON/NY":
        trade_count += 1

# ===== WIN / LOSS TRACKER =====
async def evaluate_trade(pair, direction, entry_price):
    global wins, losses, loss_streak

    await asyncio.sleep(180)

    df = get_market_data(pair)
    if df is None:
        return

    exit_price = df.iloc[-1]["close"]
    win = exit_price > entry_price if direction == "BUY" else exit_price < entry_price

    if win:
        wins += 1
        loss_streak = 0
    else:
        losses += 1
        loss_streak += 1

# ===== MAIN LOOP =====
async def main_loop():
    global trade_count, current_day, loss_streak

    asyncio.create_task(heartbeat())

    while True:
        try:
            if date.today() != current_day:
                trade_count = 0
                loss_streak = 0
                current_day = date.today()

            # Pause trading after 2 losses
            if loss_streak >= 2:
                await asyncio.sleep(300)
                loss_streak = 0

            for pair in PAIRS:
                if trade_count >= MAX_TRADES_PER_DAY:
                    break

                df = get_market_data(pair)
                direction, score, reasons, expiration = analyze_signal(df)

                if direction and score >= 90:
                    entry_price = df.iloc[-1]["close"]

                    await send_warning(pair)
                    await asyncio.sleep(60)

                    await send_signal(pair, direction, score, reasons, expiration)

                    asyncio.create_task(evaluate_trade(pair, direction, entry_price))

                await asyncio.sleep(1)

            await asyncio.sleep(MARKET_SCAN_SECONDS)

        except Exception as e:
            print("ERROR:", e)
            await asyncio.sleep(5)

# ===== START =====
if __name__ == "__main__":
    print("🚀 CRUXIFEED LEVEL-3 ELITE BOT LIVE")
    asyncio.run(main_loop())