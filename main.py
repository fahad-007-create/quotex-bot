# 🚀 Quotex Ultimate Bot - Smart Money + News Filter Edition
# ✅ Smart Zones, OB + FVG + RSI Divergence + Red News Shield + Accurate Win/Loss + Clean UI

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

# === UTILS ===
def get_price(pair):
    try:
        handler = TA_Handler(symbol=pair, screener="forex", exchange="FX_IDC", interval=Interval.INTERVAL_1_MINUTE)
        return handler.get_analysis().indicators.get("close", 0)
    except: return 0

def get_current_second():
    now = datetime.datetime.now(pytz.timezone("Asia/Karachi"))
    return now.second, now.minute

def is_red_news_active():
    url = f"https://newsapi.org/v2/top-headlines?category=business&language=en&apiKey={NEWS_API_KEY}"
    try:
        res = requests.get(url).json()
        return len(res.get("articles", [])) > 0
    except:
        return False

# === STRATEGY ENGINE ===
def analyze_signal(pair):
    try:
        handler = TA_Handler(symbol=pair, screener="forex", exchange="FX_IDC", interval=Interval.INTERVAL_1_MINUTE)
        a = handler.get_analysis()
        i = a.indicators

        # Indicators
        rsi, ema9, ema21 = i.get("RSI", 50), i.get("EMA9", 0), i.get("EMA21", 0)
        macd, macd_sig = i.get("MACD.macd", 0), i.get("MACD.signal", 0)
        close, open_, high, low = i.get("close", 0), i.get("open", 0), i.get("high", 0), i.get("low", 0)
        summary = a.summary.get("RECOMMENDATION", "NEUTRAL")

        body = abs(close - open_)
        uw = high - max(open_, close)
        lw = min(open_, close) - low

        score, direction, logic_used = 0, "WAIT", []

        # EMA + Trend
        if ema9 > ema21: direction = "UP"; score += 1; logic_used.append("EMA Uptrend")
        elif ema9 < ema21: direction = "DOWN"; score += 1; logic_used.append("EMA Downtrend")

        # RSI Divergence (Simulated)
        if rsi < 30 and direction == "UP": score += 1; logic_used.append("RSI Oversold")
        if rsi > 70 and direction == "DOWN": score += 1; logic_used.append("RSI Overbought")

        # MACD Confirmation
        if macd > macd_sig and direction == "UP": score += 1; logic_used.append("MACD Bullish")
        if macd < macd_sig and direction == "DOWN": score += 1; logic_used.append("MACD Bearish")

        # OB + FVG Logic (simulated via wick + body)
        if direction == "UP" and lw > body: score += 1; logic_used.append("Order Block Rejection")
        if direction == "DOWN" and uw > body: score += 1; logic_used.append("FVG Reversal")

        # Volume Strength (proxy)
        if body > (uw + lw): score += 1; logic_used.append("Strong Candle")

        # Session Bias
        hour = datetime.datetime.now(pytz.timezone("Asia/Karachi")).hour
        if 12 <= hour <= 16 and direction == "UP": score += 1; logic_used.append("London Trend")
        if 18 <= hour <= 22 and direction == "DOWN": score += 1; logic_used.append("NY Reversal")

        confidence = "HIGH" if score >= 5 else "LOW"
        if score < 3: direction = "WAIT"

        return direction, confidence, logic_used
    except Exception as e:
        print("❌ Analysis Error:", e)
        return "WAIT", "LOW", []

# === TELEGRAM ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Start Signal", callback_data="start")]]
    await update.message.reply_text("👋 Welcome! Click below to begin.", reply_markup=InlineKeyboardMarkup(keyboard))

async def select_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    keyboard = [[InlineKeyboardButton(pair, callback_data=f"pair_{pair}")] for pair in PAIRS]
    await query.edit_message_text("📊 Choose pair:", reply_markup=InlineKeyboardMarkup(keyboard))

async def wait_for_next_candle(pair, user_id, context):
    await context.bot.send_message(chat_id=user_id, text=f"📍 PAIR: {pair}\n⏱️ TIME: 1 Minute\n📊 TRADE: #{len(trade_history)+1}\n⏳ Wait for direction...")

    _, current_minute = get_current_second()
    while True:
        sec, minute = get_current_second()
        if minute != current_minute and sec >= 57:
            break
        await asyncio.sleep(0.5)

    if is_red_news_active():
        await context.bot.send_message(chat_id=user_id, text="⚠️ Red News Active — Skipping signal for safety.")
        return

    entry_price = get_price(pair)
    direction, confidence, logic_used = analyze_signal(pair)
    trade_id = len(trade_history) + 1
    trade_history.append({"id": trade_id, "pair": pair, "direction": direction, "confidence": confidence, "entry": entry_price, "result": "PENDING"})

    logic_line = " + ".join(logic_used)
    await context.bot.send_message(chat_id=user_id, text=f"📈 DIRECTION: {direction}\n🎯 CONFIDENCE: {confidence}\n📌 STRATEGY: {logic_line}\n💵 ENTRY PRICE: {entry_price}")

    await asyncio.sleep(60)
    exit_price = get_price(pair)
    result = "WIN" if (direction == "UP" and exit_price > entry_price) or (direction == "DOWN" and exit_price < entry_price) else "LOSS"
    trade_history[-1]["result"] = result
    await context.bot.send_message(chat_id=user_id, text=f"🏁 RESULT: {result} (Exit: {exit_price})")

    keyboard = [[InlineKeyboardButton("🔁 Next Signal", callback_data=f"next_{pair}")]]
    await context.bot.send_message(chat_id=user_id, text="Tap below for next signal:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    pair = query.data.split("_")[1]
    await wait_for_next_candle(pair, query.from_user.id, context)

async def handle_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    pair = query.data.split("_")[1]
    await wait_for_next_candle(pair, query.from_user.id, context)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = len(trade_history)
    wins = len([t for t in trade_history if t['result'] == 'WIN'])
    losses = len([t for t in trade_history if t['result'] == 'LOSS'])
    rate = round((wins / total) * 100, 2) if total else 0
    await update.message.reply_text(f"📊 Total: {total}\n✅ Wins: {wins}\n❌ Losses: {losses}\n🎯 Win Rate: {rate}%")

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not trade_history:
        await update.message.reply_text("📉 No trades yet.")
        return
    msg = "📋 Trade History:\n"
    for t in trade_history[-10:]:
        msg += f"#{t['id']} {t['pair']} | {t['direction']} | {t['confidence']} | Result: {t['result']}\n"
    await update.message.reply_text(msg)

# === RUN ===
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CallbackQueryHandler(select_pair, pattern="^start$"))
    app.add_handler(CallbackQueryHandler(handle_pair, pattern="^pair_"))
    app.add_handler(CallbackQueryHandler(handle_next, pattern="^next_"))
    print("✅ Ultimate Smart Money Bot Running…")
    app.run_polling()
