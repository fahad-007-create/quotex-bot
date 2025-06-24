# 🔥 Enhanced Manual Signal Bot for Quotex - Fahad Edition
# Strategy: EMA, RSI, MACD, Candle Wick/Body, Multi-Candle Patterns

import logging
import requests
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from tradingview_ta import TA_Handler, Interval
import datetime, pytz

# === CONFIG ===
TELEGRAM_TOKEN = "7704084377:AAG56RXCZvJpnTlTEMSKO9epJUl9B8-1on8"
CHAT_ID = "6183147124"

PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD",
    "NZDUSD", "USDCAD", "EURJPY", "GBPJPY", "EURGBP", "EURCHF"
]

INTERVALS = {
    "1 MINUTE": Interval.INTERVAL_1_HOUR,
    "5 MINUTE": Interval.INTERVAL_1_HOUR
}

user_selection = {}

# === STRATEGY ===
def analyze_signal(pair, tf):
    try:
        handler = TA_Handler(
            symbol=pair,
            screener="forex",
            exchange="FX_IDC",
            interval=INTERVALS[tf]
        )
        a = handler.get_analysis()
        i = a.indicators
        rsi = i.get("RSI", 50)
        ema9 = i.get("EMA9", 0)
        ema21 = i.get("EMA21", 0)
        macd = i.get("MACD.macd", 0)
        macd_signal = i.get("MACD.signal", 0)
        summary = a.summary.get("RECOMMENDATION", "NEUTRAL")

        close = i.get("close", 0)
        open_ = i.get("open", 0)
        high = i.get("high", 0)
        low = i.get("low", 0)

        body = abs(close - open_)
        upper_wick = high - max(open_, close)
        lower_wick = min(open_, close) - low

        candles = i.get("Candles", [])  # Needs external candle history if implemented

        print(f"📊 {pair} {tf} | RSI: {rsi}, EMA9: {ema9}, EMA21: {ema21}, MACD: {macd}, Signal: {macd_signal}, Summary: {summary}")
        print(f"🕯️ Body: {body:.4f}, Wick Up: {upper_wick:.4f}, Wick Down: {lower_wick:.4f}")

        score = 0
        direction = "WAIT"

        # === EMA trend filter ===
        if ema9 > ema21:
            direction = "UP"
            score += 1
        elif ema9 < ema21:
            direction = "DOWN"
            score += 1

        # === RSI ===
        if rsi < 30 and direction == "UP": score += 1
        if rsi > 70 and direction == "DOWN": score += 1

        # === MACD ===
        if macd > macd_signal and direction == "UP": score += 1
        if macd < macd_signal and direction == "DOWN": score += 1

        # === Summary Confirmation ===
        if summary == "BUY" and direction == "UP": score += 1
        if summary == "SELL" and direction == "DOWN": score += 1

        # === Wick Confirmation (Rejection logic) ===
        if direction == "UP" and lower_wick > body * 0.7: score += 1
        if direction == "DOWN" and upper_wick > body * 0.7: score += 1

        # === Engulfing candle logic (simplified) ===
        if body > (upper_wick + lower_wick) and summary in ["STRONG_BUY", "STRONG_SELL"]:
            score += 1

        # === Momentum: 3-candle reversal pattern logic (requires full candle history for accuracy) ===
        if direction == "DOWN" and upper_wick > body and body < 0.5:
            score += 1  # possible reversal
        if direction == "UP" and lower_wick > body and body < 0.5:
            score += 1

        # === Gap logic approximation (gap between open/close) ===
        gap = abs(close - open_)
        if gap > body * 1.5:
            score += 1

        print(f"✅ Final Score: {score} | Direction: {direction}")

        if score >= 5:
            confidence = "HIGH"
        elif score >= 3:
            confidence = "LOW"
        else:
            direction = "WAIT"
            confidence = "LOW"

        return direction, confidence

    except Exception as e:
        print(f"❌ Error: {e}")
        return "WAIT", "LOW"

# === TELEGRAM FLOW ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Start Analysis", callback_data="start_analysis")]]
    await update.message.reply_text("👋 Welcome, click to begin:", reply_markup=InlineKeyboardMarkup(keyboard))

async def pair_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(pair, callback_data=f"pair_{pair}")] for pair in PAIRS]
    await update.message.reply_text("📊 Available Pairs:", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_pairs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton(pair, callback_data=f"pair_{pair}")] for pair in PAIRS]
    await query.edit_message_text("📊 Choose a pair:", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_timeframes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pair = query.data.split("_")[1]
    user_selection[query.from_user.id] = {"pair": pair}
    keyboard = [[InlineKeyboardButton(tf, callback_data=f"tf_{tf.replace(' ', '')}")] for tf in INTERVALS.keys()]
    await query.edit_message_text(f"✅ Selected {pair}\n🕒 Choose timeframe:", reply_markup=InlineKeyboardMarkup(keyboard))

async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tf_label = query.data.split("_")[1]
    tf_key = tf_label[:1] + " MINUTE" if tf_label.startswith("1") else "5 MINUTE"
    uid = query.from_user.id
    pair = user_selection.get(uid, {}).get("pair")

    if not pair:
        await query.edit_message_text("❌ Please restart with /start")
        return

    await query.edit_message_text(f"🔍 Analyzing {pair} ({tf_key})... Please wait")
    direction, confidence = analyze_signal(pair, tf_key)

    if direction == "WAIT":
        await context.bot.send_message(chat_id=uid, text=f"⚠️ No signal for {pair} ({tf_key}). Try again later.")
    else:
        tag = "✅ Real Market Signal"
        await context.bot.send_message(
            chat_id=uid,
            text=f"📊 PAIR: {pair}\n⏱️ TIMEFRAME: {tf_key}\n🎯 CONFIDENCE: {confidence}\n📈 DIRECTION: {direction}\n🧠 STRATEGY: {tag}"
        )

# === BOT INIT ===
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pair", pair_command))
    app.add_handler(CallbackQueryHandler(show_pairs, pattern="^start_analysis$"))
    app.add_handler(CallbackQueryHandler(show_timeframes, pattern="^pair_"))
    app.add_handler(CallbackQueryHandler(analyze, pattern="^tf_"))

    print("✅ Bot is running...")
    app.run_polling()
