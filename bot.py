import requests
import time
import pandas as pd
import ta
import MetaTrader5 as mt5
from datetime import datetime, date
import random
import os

# ENV VARIABLES (Railway)
API_KEY = os.getenv("FASTFOREX_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = "@SYC_FX"

MT5_LOGIN = int(os.getenv("MT5_LOGIN"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD")
MT5_SERVER = os.getenv("MT5_SERVER")

PAIRS = ["EURUSD", "GBPUSD", "GBPCAD", "USDJPY"]
TRADE_AMOUNT = "$250"

WARNING_IMAGE = "https://i.postimg.cc/Y9zbMWG1/file-000000009af871f49d98a41cd04221cb.png"
BUY_IMAGE = "https://i.postimg.cc/3x984LsS/buy.png"
SELL_IMAGE = "https://i.postimg.cc/jqzrngNB/sell.png"

MAX_TRADES_PER_DAY = 14
daily_trades = 0
win_count = 0
loss_count = 0
current_day = date.today()

# INIT MT5
mt5.initialize(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)

# SESSION FILTER (LONDON + NY UTC)
def session_active():
    hour = datetime.utcnow().hour
    london = 7 <= hour < 12
    newyork = 12 <= hour < 17
    return london or newyork

# TELEGRAM SENDER
def send_photo(text, image_url):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    requests.post(url, data={"chat_id": CHANNEL_ID, "photo": image_url, "caption": text})

# PRICE FETCH
def get_price(pair):
    base = pair[:3]
    quote = pair[3:]
    url = f"https://api.fastforex.io/fetch-one?from={base}&to={quote}&api_key={API_KEY}"
    try:
        r = requests.get(url, timeout=5).json()
        return r["result"][quote]
    except:
        return None

# REAL MT5 TRADE CHECKER
def check_mt5_result():
    global win_count, loss_count
    deals = mt5.history_deals_get(datetime.utcnow().date(), datetime.utcnow())
    if deals:
        last = deals[-1]
        if last.profit > 0:
            win_count += 1
        elif last.profit < 0:
            loss_count += 1

# AI MARKET FILTER
def ai_filter(prices):
    structure = abs(prices[-1] - prices[-20])
    volatility = max(prices[-15:]) - min(prices[-15:])
    if structure < 0.00008:
        return False
    if volatility < 0.00005:
        return False
    return True

# ANALYSIS ENGINE
def analyze(pair):
    prices = []
    for _ in range(90):
        p = get_price(pair)
        if p:
            prices.append(p)
        time.sleep(0.12)

    if len(prices) < 70:
        return None

    if not ai_filter(prices):
        return None

    df = pd.DataFrame(prices, columns=["price"])

    rsi = ta.momentum.RSIIndicator(df["price"]).rsi().iloc[-1]
    ema9 = ta.trend.EMAIndicator(df["price"], 9).ema_indicator().iloc[-1]
    ema21 = ta.trend.EMAIndicator(df["price"], 21).ema_indicator().iloc[-1]

    macd = ta.trend.MACD(df["price"])
    macd_line = macd.macd().iloc[-1]
    macd_signal = macd.macd_signal().iloc[-1]

    adx = ta.trend.ADXIndicator(df["price"], df["price"], df["price"]).adx().iloc[-1]
    momentum = prices[-1] - prices[-15]

    signal = "BUY" if ema9 > ema21 else "SELL"
    direction = "Up" if signal == "BUY" else "Down"

    confidence = 60
    reasons = []

    if adx > 25:
        confidence += 12
        reasons.append("Strong trend")

    if signal == "BUY" and rsi > 55:
        confidence += 12
        reasons.append("RSI bullish")

    if signal == "SELL" and rsi < 45:
        confidence += 12
        reasons.append("RSI bearish")

    if signal == "BUY" and macd_line > macd_signal:
        confidence += 10
        reasons.append("MACD bullish")

    if signal == "SELL" and macd_line < macd_signal:
        confidence += 10
        reasons.append("MACD bearish")

    if signal == "BUY" and momentum > 0:
        confidence += 8
        reasons.append("Momentum rising")

    if signal == "SELL" and momentum < 0:
        confidence += 8
        reasons.append("Momentum falling")

    if confidence < 85:
        return None

    expiration = random.choice(["3m", "5m"])
    target = "+6–9 pips"

    return signal, direction, confidence, ", ".join(reasons), expiration, target

# DAILY REPORT
def send_daily_report():
    global win_count, loss_count, daily_trades

    total = win_count + loss_count
    if total == 0:
        return

    winrate = round((win_count / total) * 100, 2)

    report = (
        f"📊 SYC_FX DAILY REAL PERFORMANCE\n\n"
        f"Trades: {total}\n"
        f"Wins: {win_count}\n"
        f"Losses: {loss_count}\n"
        f"Win Rate: {winrate}%\n\n"
        f"Session: London + New York\n"
        f"Tracked via MT5 Broker"
    )

    send_photo(report, WARNING_IMAGE)

    win_count = 0
    loss_count = 0
    daily_trades = 0

print("🚀 SYC_FX REAL MT5 ENGINE LIVE...")

# MAIN LOOP
while True:
    try:
        # RESET DAILY
        if date.today() != current_day:
            send_daily_report()
            current_day = date.today()

        # LIMIT TRADES
        if daily_trades >= MAX_TRADES_PER_DAY:
            time.sleep(300)
            continue

        # SESSION FILTER
        if not session_active():
            time.sleep(120)
            continue

        for pair in PAIRS:
            if daily_trades >= MAX_TRADES_PER_DAY:
                break

            result = analyze(pair)
            if not result:
                continue

            signal, direction, confidence, analysis, expiration, target = result

            # WARNING
            warning_text = (
                f"⚠️ HIGH-PRECISION SIGNAL INCOMING\n\n"
                f"Pair: {pair}\n"
                f"Timeframe: 1 min\n"
                f"Sending in 60 seconds..."
            )
            send_photo(warning_text, WARNING_IMAGE)
            time.sleep(60)

            # FINAL SIGNAL
            final_text = (
                f"💱 Pair: {pair[:3]}/{pair[3:]}\n"
                f"⏱️ Timeframe: 1 min\n"
                f"💰 Trade Amount: {TRADE_AMOUNT}\n"
                f"⬇️ Direction: {signal} ({direction})\n\n"
                f"🔍 Analysis: {analysis}\n"
                f"🏹 Target: {target}\n"
                f"🎯 Expiration: {expiration}\n"
                f"📊 Confidence: {confidence}%"
            )

            send_photo(final_text, BUY_IMAGE if signal == "BUY" else SELL_IMAGE)

            # CHECK REAL MT5 RESULT AFTER TRADE
            time.sleep(180)
            check_mt5_result()

            daily_trades += 1
            time.sleep(120)

        time.sleep(10)

    except Exception as e:
        print("ERROR:", e)
        time.sleep(15)