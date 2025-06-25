# ✅ Expert v5.0 Bot - Ultra-Confirmation Strategy via /startv5
# 📊 Uses EMA 50/200 + Break & Retest + MACD Spike + Wick Trap Logic

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
trade_history_v5 = []

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
def analyze_expert_v5(pair):
    i = get_analysis(pair)
    if not i: return "WAIT", "LOW", ["No Data"]

    ema50, ema200 = i.get("EMA50", 0), i.get("EMA200", 0)
    macd, macd_sig, hist = i.get("MACD.macd", 0), i.get("MACD.signal", 0), i.get("MACD.histogram", 0)
    close, open_, high, low = i.get("close", 0), i.get("open", 0), i.get("high", 0), i.get("low", 0)
    body = abs(close - open_)
    wick_up, wick_down = high - max(open_, close), min(open_, close) - low

    direction = "WAIT"
    score = 0
    logic = []

    # EMA Trend Filter
    if ema50 > ema200:
        direction = "UP"
        score += 1
        logic.append("EMA Bull Trend")
    elif ema50 < ema200:
        direction = "DOWN"
        score += 1
        logic.append("EMA Bear Trend")
    else:
        logic.append("EMA Flat")

    # Break & Retest (Simplified by Wick Trap)
    if direction == "UP" and wick_down > body:
        score += 1
        logic.append("Wick Trap Bull")
    elif direction == "DOWN" and wick_up > body:
        score += 1
        logic.append("Wick Trap Bear")

    # MACD Momentum Spike
    if direction == "UP" and macd > macd_sig and hist > 0.05:
        score += 1
        logic.append("MACD Bull Spike")
    elif direction == "DOWN" and macd < macd_sig and hist < -0.05:
        score += 1
        logic.append("MACD Bear Spike")

    # Final Confirmation
    if score >= 3:
        return direction, "HIGH", logic
    else:
        return "WAIT", "LOW", logic

# === TELEGRAM COMMAND /startv5 ===
async def startv5(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(pair, callback_data=f"v5_{pair}")] for pair in PAIRS]
    await update.message.reply_text("🔍 Select a pair for Expert v5.0:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_v5(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pair = query.data.split("_")[1]
    user_id = query.from_user.id

    await context.bot.send_message(chat_id=user_id, text=f"🧠 Analyzing {pair} deeply. Please wait 2–3 minutes...")

    # Wait for next candle
    _, start_min = get_current_second()
    while True:
        s, m = get_current_second()
        if m != start_min and s >= 58:
            break
        await asyncio.sleep(0.5)

    entry = get_analysis(pair).get("close", 0)
    direction, confidence, logic_used = analyze_expert_v5(pair)

    if direction == "WAIT":
        await context.bot.send_message(chat_id=user_id, text=f"⚠️ No Ultra-Confirmed Signal. Try again later.")
        return

    logic_line = " + ".join(logic_used)
    trade_id = len(trade_history_v5) + 1
    trade_history_v5.append({"id": trade_id, "pair": pair, "direction": direction, "confidence": confidence, "entry": entry, "result": "PENDING"})

    await context.bot.send_message(chat_id=user_id, text=f"📍 {pair} | Expert v5.0
📈 Direction: {direction}
🎯 Confidence: {confidence}
📌 Logic: {logic_line}
💵 Entry: {entry}")

    await asyncio.sleep(60)
    exit_price = get_analysis(pair).get("close", 0)
    result = "WIN" if (direction == "UP" and exit_price > entry) or (direction == "DOWN" and exit_price < entry) else "LOSS"
    trade_history_v5[-1]["result"] = result
    await context.bot.send_message(chat_id=user_id, text=f"🏁 RESULT: {result} (Exit: {exit_price})")

    keyboard = [[InlineKeyboardButton("🔁 Next v5 Signal", callback_data=f"v5_{pair}")]]
    await context.bot.send_message(chat_id=user_id, text="Tap below for next v5 signal:", reply_markup=InlineKeyboardMarkup(keyboard))

# === MAIN ===
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("startv5", startv5))
    app.add_handler(CallbackQueryHandler(handle_v5, pattern="^v5_"))
    print("✅ Expert v5.0 Bot Running...")
    app.run_polling()
