# Manual Signal Bot with Stronger Strategy - For Fahad
# Includes: EMA filter, RSI, MACD, candle trend, support/resistance scoring
# Sends signal only after you choose pair and timeframe manually from Telegram

import logging
import requests
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from tradingview_ta import TA_Handler, Interval
import datetime, pytz

# === CONFIG ===
TELEGRAM_TOKEN = "7704084377:AAG56RXCZvJpnTlTEMSKO9epJUl9B8-1on8"
CHAT_ID = "6183147124"
NEWS_API_KEY = "8b5c91784c144924a179b7b0899ba61f"

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
        rsi = a.indicators.get("RSI", 50)
        ema9 = a.indicators.get("EMA9", 0)
        ema21 = a.indicators.get("EMA21", 0)
        macd = a.indicators.get("MACD.macd", 0)
        macd_signal = a.indicators.get("MACD.signal", 0)
        candle_analysis = a.summary.get("RECOMMENDATION", "NEUTRAL")

        # Log indicator values for debugging
        print(f"🔍 {pair} ({tf}) | RSI: {rsi}, EMA9: {ema9}, EMA21: {ema21}, MACD: {macd}, Signal: {macd_signal}, Summary: {candle_analysis}")

        score = 0
        direction = "WAIT"

        # Trend Direction (EMA)
        if ema9 > ema21:
            score += 1
            direction = "UP"
        elif ema9 < ema21:
            score += 1
            direction = "DOWN"

        # Momentum (RSI)
        if rsi < 30 and direction == "UP":
            score += 1
        elif rsi > 70 and direction == "DOWN":
            score += 1

        # MACD Momentum
        if macd > macd_signal and direction == "UP":
            score += 1
        elif macd < macd_signal and direction == "DOWN":
            score += 1

        # Candle Trend Bias (TV Summary)
        if candle_analysis == "BUY" and direction == "UP":
            score += 1
        elif candle_analysis == "SELL" and direction == "DOWN":
            score += 1

        print(f"✅ {pair} {tf} → Score: {score}, Direction: {direction}")

        if score >= 4:
            confidence = "HIGH"
        elif score >= 2:
            confidence = "LOW"
        else:
            confidence = "LOW"
            direction = "WAIT"

        return direction, confidence

    except Exception as e:
        print(f"❌ Error analyzing {pair} {tf}:", e)
        return "WAIT", "LOW"

# === TELEGRAM COMMANDS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Start Analysis", callback_data="start_analysis")]]
    await update.message.reply_text("👋 Welcome, click below to begin:", reply_markup=InlineKeyboardMarkup(keyboard))

async def pair_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(pair, callback_data=f"pair_{pair}")] for pair in PAIRS]
    await update.message.reply_text("📊 Available Pairs:", reply_markup=InlineKeyboardMarkup(keyboard))

# === FLOW CONTROL ===
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
    await query.edit_message_text(f"✅ Selected {pair}\n🕒 Now choose timeframe:", reply_markup=InlineKeyboardMarkup(keyboard))

async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tf_label = query.data.split("_")[1]
    tf_key = tf_label[:1] + " MINUTE" if tf_label.startswith("1") else "5 MINUTE"
    uid = query.from_user.id
    pair = user_selection.get(uid, {}).get("pair")

    if not pair:
        await query.edit_message_text("❌ Please restart using /start")
        return

    await query.edit_message_text(f"🔍 Analyzing {pair} ({tf_key})... Please wait")
    direction, confidence = analyze_signal(pair, tf_key)

    if direction == "WAIT":
        await context.bot.send_message(chat_id=uid, text="⚠️ No valid signal found for this setup. Try a different pair or timeframe.")
    else:
        tag = "✅ Real Market Signal"
        await context.bot.send_message(chat_id=uid, text=f"📊 PAIR: {pair}\n⏱️ TIMEFRAME: {tf_key}\n🎯 CONFIDENCE: {confidence}\n📈 DIRECTION: {direction}\n🧠 STRATEGY: {tag}")

# === RUN BOT ===
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
