# ✅ Quotex Bot (Expert v5.0 + Normal Fast Mode)
# ✅ /start = Fast Signal Mode
# ✅ /startv5 = Ultra Confirmation Mode

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
trade_history = []
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

# === STRATEGY v5 ===
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

    if ema50 > ema200:
        direction = "UP"; score += 1; logic.append("EMA Bull Trend")
    elif ema50 < ema200:
        direction = "DOWN"; score += 1; logic.append("EMA Bear Trend")
    else:
        logic.append("EMA Flat")

    if direction == "UP" and wick_down > body:
        score += 1; logic.append("Wick Trap Bull")
    elif direction == "DOWN" and wick_up > body:
        score += 1; logic.append("Wick Trap Bear")

    if direction == "UP" and macd > macd_sig and hist > 0.05:
        score += 1; logic.append("MACD Bull Spike")
    elif direction == "DOWN" and macd < macd_sig and hist < -0.05:
        score += 1; logic.append("MACD Bear Spike")

    if score >= 3:
        return direction, "HIGH", logic
    else:
        return "WAIT", "LOW", logic

# === STRATEGY FAST ===
def analyze_fast(pair):
    i = get_analysis(pair)
    if not i: return "UP", "LOW", ["No Data"]
    rsi, ema9, ema21 = i.get("RSI", 50), i.get("EMA9", 0), i.get("EMA21", 0)
    macd, macd_sig = i.get("MACD.macd", 0), i.get("MACD.signal", 0)
    close, open_, high, low = i.get("close", 0), i.get("open", 0), i.get("high", 0), i.get("low", 0)
    body = abs(close - open_)
    uw, lw = high - max(open_, close), min(open_, close) - low
    score, logic, direction = 0, [], "WAIT"

    if ema9 > ema21: direction, score = "UP", 1; logic.append("EMA Up")
    elif ema9 < ema21: direction, score = "DOWN", 1; logic.append("EMA Down")
    if direction == "UP" and rsi < 30: score += 1; logic.append("RSI Oversold")
    if direction == "DOWN" and rsi > 70: score += 1; logic.append("RSI Overbought")
    if direction == "UP" and macd > macd_sig: score += 1; logic.append("MACD Bull")
    if direction == "DOWN" and macd < macd_sig: score += 1; logic.append("MACD Bear")
    if direction == "UP" and lw > body: score += 1; logic.append("Wick Rejection")
    if direction == "DOWN" and uw > body: score += 1; logic.append("Wick Trap")
    if body > (uw + lw): score += 1; logic.append("Momentum Candle")
    if score < 3: direction = "UP" if close > open_ else "DOWN"; logic.append("Forced Signal")
    confidence = "HIGH" if score >= 4 else "MODERATE"
    return direction, confidence, logic

# === TELEGRAM HANDLERS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Start Signal", callback_data="start")]]
    await update.message.reply_text("👋 Welcome! Click below to begin:", reply_markup=InlineKeyboardMarkup(keyboard))

async def startv5(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(pair, callback_data=f"v5_{pair}")] for pair in PAIRS]
    await update.message.reply_text("🔍 Select a pair for Expert v5.0:", reply_markup=InlineKeyboardMarkup(keyboard))

async def select_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    keyboard = [[InlineKeyboardButton(pair, callback_data=f"pair_{pair}")] for pair in PAIRS]
    await query.edit_message_text("📊 Choose a pair:", reply_markup=InlineKeyboardMarkup(keyboard))

async def wait_signal(pair, user_id, context, mode):
    await context.bot.send_message(chat_id=user_id, text=f"📍 {pair} | Mode: {mode}\n⌛ Analyzing...")
    _, m_start = get_current_second()
    while True:
        s, m = get_current_second()
        if m != m_start and s >= 58: break
        await asyncio.sleep(0.5)

    entry = get_analysis(pair).get("close", 0)
    direction, confidence, logic = analyze_expert_v5(pair) if mode == "v5" else analyze_fast(pair)
    history = trade_history_v5 if mode == "v5" else trade_history
    if direction == "WAIT":
        await context.bot.send_message(chat_id=user_id, text="⚠️ No Confirmed Signal. Try again.")
        return
    logic_text = " + ".join(logic)
    trade_id = len(history) + 1
    history.append({"id": trade_id, "pair": pair, "direction": direction, "confidence": confidence, "entry": entry, "result": "PENDING"})

    await context.bot.send_message(chat_id=user_id, text=f"📍 {pair} | {mode.upper()}\n📈 Direction: {direction}\n🎯 Confidence: {confidence}\n📌 Logic: {logic_text}\n💵 Entry: {entry}")

    await asyncio.sleep(60)
    exit_price = get_analysis(pair).get("close", 0)
    result = "WIN" if (direction == "UP" and exit_price > entry) or (direction == "DOWN" and exit_price < entry) else "LOSS"
    history[-1]["result"] = result
    await context.bot.send_message(chat_id=user_id, text=f"🏁 RESULT: {result} (Exit: {exit_price})")

    next_label = "🔁 Next v5 Signal" if mode == "v5" else "🔁 Next Signal"
    await context.bot.send_message(chat_id=user_id, text="Tap below for next signal:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(next_label, callback_data=f"{mode}_{pair}")]]))

async def handle_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    pair = query.data.split("_")[1]
    mode = "v5" if query.data.startswith("v5_") else "fast"
    await wait_signal(pair, query.from_user.id, context, mode)

# === MAIN ===
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("startv5", startv5))
    app.add_handler(CallbackQueryHandler(select_pair, pattern="^start$"))
    app.add_handler(CallbackQueryHandler(handle_pair, pattern="^(pair_|v5_|fast_).*$"))
    print("✅ Quotex Expert Bot Running...")
    app.run_polling()
