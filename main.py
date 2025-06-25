# ✅ Quotex Sniper Bot - Final Smart Logic Upgrade (Fahad v1.0)
# ✅ Dynamic Scoring, Fast Signals, High Accuracy, Clean Format, Real-Time Candle Sync

import logging
import requests
import datetime
import pytz
import asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from tradingview_ta import TA_Handler, Interval

# === CONFIG ===
TELEGRAM_TOKEN = "7704084377:AAG56RXCZvJpnTlTEMSKO9epJUl9B8-1on8"
CHAT_ID = "6183147124"
NEWS_API_KEY = "8b5c91784c144924a179b7b0899ba61f"
PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD", "USDCAD", "EURJPY", "GBPJPY", "EURGBP", "EURCHF"]
user_selection = {}
trade_history = []

# === UTILITY ===
def get_price(pair):
    try:
        handler = TA_Handler(symbol=pair, screener="forex", exchange="FX_IDC", interval=Interval.INTERVAL_1_MINUTE)
        return handler.get_analysis().indicators.get("close", 0)
    except:
        return None

def get_current_second():
    now = datetime.datetime.now(pytz.timezone("Asia/Karachi"))
    return now.second, now.minute

def is_red_news_active():
    url = f"https://newsapi.org/v2/top-headlines?category=business&language=en&apiKey={NEWS_API_KEY}"
    try:
        res = requests.get(url).json()
        articles = res.get("articles", [])
        now = datetime.datetime.utcnow()
        for article in articles:
            published = article.get("publishedAt")
            if published:
                pub_time = datetime.datetime.strptime(published, "%Y-%m-%dT%H:%M:%SZ")
                diff = abs((now - pub_time).total_seconds() / 60)
                if diff <= 5:
                    return True
    except:
        pass
    return False

# === STRATEGY ===
def detect_pattern(open_, close, high, low):
    body = abs(close - open_)
    upper_wick = high - max(open_, close)
    lower_wick = min(open_, close) - low
    is_bullish = close > open_
    is_bearish = close < open_
    patterns = []

    if is_bullish and body > upper_wick and body > lower_wick:
        patterns.append("Bullish Marubozu")
    if is_bearish and body > upper_wick and body > lower_wick:
        patterns.append("Bearish Marubozu")
    if lower_wick > body * 2 and is_bullish:
        patterns.append("Hammer")
    if upper_wick > body * 2 and is_bearish:
        patterns.append("Shooting Star")
    if abs(close - open_) <= (high - low) * 0.1:
        patterns.append("Doji")
    return patterns

def analyze_signal(pair):
    try:
        handler = TA_Handler(symbol=pair, screener="forex", exchange="FX_IDC", interval=Interval.INTERVAL_1_MINUTE)
        a = handler.get_analysis()
        i = a.indicators

        rsi, ema9, ema21 = i.get("RSI", 50), i.get("EMA9", 0), i.get("EMA21", 0)
        macd, macd_sig = i.get("MACD.macd", 0), i.get("MACD.signal", 0)
        close, open_, high, low = i.get("close", 0), i.get("open", 0), i.get("high", 0), i.get("low", 0)

        if not all([rsi, ema9, ema21, close, open_, high, low]):
            return "WAIT", "LOW", ["Analysis Failed"]

        body = abs(close - open_)
        uw = high - max(open_, close)
        lw = min(open_, close) - low

        score = 0
        direction = "WAIT"
        logic_used = []

        if ema9 > ema21:
            direction = "UP"
            score += 1
            logic_used.append("EMA Uptrend")
        elif ema9 < ema21:
            direction = "DOWN"
            score += 1
            logic_used.append("EMA Downtrend")

        if rsi < 30 and direction == "UP":
            score += 1
            logic_used.append("RSI Oversold")
        elif rsi > 70 and direction == "DOWN":
            score += 1
            logic_used.append("RSI Overbought")

        if macd > macd_sig and direction == "UP":
            score += 1
            logic_used.append("MACD Bullish")
        elif macd < macd_sig and direction == "DOWN":
            score += 1
            logic_used.append("MACD Bearish")

        if direction == "UP" and lw > body:
            score += 1
            logic_used.append("OB Rejection Wick")
        if direction == "DOWN" and uw > body:
            score += 1
            logic_used.append("FVG Upper Wick")

        if body > (uw + lw):
            score += 1
            logic_used.append("Momentum Candle")

        patterns = detect_pattern(open_, close, high, low)
        logic_used += patterns

        if "Hammer" in patterns and direction == "UP":
            score += 1
        if "Shooting Star" in patterns and direction == "DOWN":
            score += 1

        confidence = "HIGH" if score >= 4 else "LOW"
        if score < 3:
            direction = "WAIT"

        return direction, confidence, logic_used
    except Exception as e:
        print("❌ Analysis Error:", e)
        return "WAIT", "LOW", ["Analysis Exception"]

# === REST OF CODE STAYS UNCHANGED ===
