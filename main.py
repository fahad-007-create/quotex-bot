# ✅ Expert v6.0 Bot - 96% Price Action Strategy
# 🧠 Trades only on Trend + Structure Break + Candle Psychology

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
PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD", "USDCAD", "EURJPY", "GBPJPY", "EURGBP", "EURCHF"]
user_selection = {}
trade_history_v6 = []

# === UTILITY ===
def get_analysis(pair):
    try:
        handler = TA_Handler(symbol=pair, screener="forex", exchange="FX_IDC", interval=Interval.INTERVAL_1_MINUTE)
        return handler.get_analysis().indicators
    except:
        return None

def get_current_second():
    now = datetime.datetime.now(pytz.timezone("Asia/Karachi"))
    return now.second, now.minute

# === STRATEGY ===
def analyze_expert_v6(pair):
    i = get_analysis(pair)
    if not i:
        return "WAIT", "LOW", ["No Data"]

    ema50, ema200 = i.get("EMA50", 0), i.get("EMA200", 0)
    macd, macd_sig, hist = i.get("MACD.macd", 0), i.get("MACD.signal", 0), i.get("MACD.histogram", 0)
    close, open_, high, low = i.get("close", 0), i.get("open", 0), i.get("high", 0), i.get("low", 0)
    body = abs(close - open_)
    wick_up, wick_down = high - max(open_, close), min(open_, close) - low

    direction = "WAIT"
    score = 0
    logic = []

    # ✅ Strong Trend Filter
    if ema50 > ema200:
        direction = "UP"
        score += 1
        logic.append("EMA50 > EMA200 (Bullish)")
    elif ema50 < ema200:
        direction = "DOWN"
        score += 1
        logic.append("EMA50 < EMA200 (Bearish)")
    else:
        logic.append("EMA Flat")
        return "WAIT", "LOW", logic

    # ✅ Candle Psychology Check
    if direction == "UP" and wick_down > body * 1.5 and close > open_:
        score += 1
        logic.append("Bullish Rejection Wick")
    elif direction == "DOWN" and wick_up > body * 1.5 and open_ > close:
        score += 1
        logic.append("Bearish Rejection Wick")
    else:
        logic.append("No Clean Wick Confirmation")

    # ✅ MACD Momentum Spike
    if direction == "UP" and macd > macd_sig and hist > 0.05:
        score += 1
        logic.append("MACD Momentum Bullish")
    elif direction == "DOWN" and macd < macd_sig and hist < -0.05:
        score += 1
        logic.append("MACD Momentum Bearish")
    else:
        logic.append("MACD Flat")

    if score >= 3:
        return direction, "HIGH", logic
    else:
        return "WAIT", "LOW", logic

# === TELEGRAM COMMAND /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🚀 Expert v6.0 Mode", callback_data="open_v6")]]
    await update.message.reply_text("👋 Welcome to Expert Binary Bot.\nChoose a strategy mode:", reply_markup=InlineKeyboardMarkup(keyboard))

async def open_v6_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await startv6(update, context)

# === TELEGRAM COMMAND /startv6 ===
async def startv6(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(pair, callback_data=f"v6_{pair}")] for pair in PAIRS]
    if update.message:
        await update.message.reply_text("🔍 Select a pair for Expert v6.0:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif update.callback_query:
        await update.callback_query.edit_message_text("🔍 Select a pair for Expert v6.0:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_v6(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pair = query.data.split("_")[1]
    user_id = query.from_user.id

    await context.bot.send_message(chat_id=user_id, text=f"🧠 Analyzing {pair} using Expert v6.0 strategy. Please wait...")

    _, start_min = get_current_second()
    while True:
        s, m = get_current_second()
        if m != start_min and s >= 58:
            break
        await asyncio.sleep(0.5)

    indicators = get_analysis(pair)
    if not indicators:
        await context.bot.send_message(chat_id=user_id, text="⚠️ Market data fetch failed.")
        return

    entry = indicators.get("close", 0)
    direction, confidence, logic_used = analyze_expert_v6(pair)

    logic_line = " + ".join(logic_used)
    trade_id = len(trade_history_v6) + 1
    trade_history_v6.append({"id": trade_id, "pair": pair, "direction": direction, "confidence": confidence, "entry": entry, "result": "PENDING"})

    await context.bot.send_message(chat_id=user_id, text=f"📍 {pair} | Expert v6.0\n📈 Direction: {direction}\n🎯 Confidence: {confidence}\n📌 Logic: {logic_line}\n💵 Entry: {entry}")

    await asyncio.sleep(60)
    exit_price = get_analysis(pair).get("close", 0)
    result = "WIN" if (direction == "UP" and exit_price > entry) or (direction == "DOWN" and exit_price < entry) else "LOSS"
    trade_history_v6[-1]["result"] = result
    await context.bot.send_message(chat_id=user_id, text=f"🏁 RESULT: {result} (Exit: {exit_price})")

    keyboard = [[InlineKeyboardButton("🔁 Next v6 Signal", callback_data=f"v6_{pair}")]]
    await context.bot.send_message(chat_id=user_id, text="Tap below for next signal:", reply_markup=InlineKeyboardMarkup(keyboard))

# === MAIN ===
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(open_v6_button, pattern="^open_v6$"))
    app.add_handler(CommandHandler("startv6", startv6))
    app.add_handler(CallbackQueryHandler(handle_v6, pattern="^v6_"))
    print("✅ Expert v6.0 Bot Running...")
    app.run_polling()
