
# ✅ Quotex Sniper Bot - Fully Fixed with Candle Color Win Detection + Live Stats Display

import logging
import requests
import datetime
import pytz
import asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from tradingview_ta import TA_Handler, Interval

TELEGRAM_TOKEN = "7704084377:AAG56RXCZvJpnTlTEMSKO9epJUl9B8-1on8"
CHAT_ID = "6183147124"
NEWS_API_KEY = "8b5c91784c144924a179b7b0899ba61f"
PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD", "USDCAD",
    "EURJPY", "GBPJPY", "EURGBP", "EURCHF", "CADJPY", "AUDJPY", "EURCAD", "AUDCAD",
    "NZDJPY", "CHFJPY", "USDHKD", "EURNZD", "GBPAUD"
]
user_selection = {}
trade_history = []

# === Utilities ===
def get_current_time():
    return datetime.datetime.now(pytz.timezone("Asia/Karachi"))

def is_red_news():
    try:
        res = requests.get(f"https://newsapi.org/v2/top-headlines?category=business&language=en&apiKey={NEWS_API_KEY}").json()
        articles = res.get("articles", [])
        now = datetime.datetime.utcnow()
        for article in articles:
            published = article.get("publishedAt")
            if published:
                pub_time = datetime.datetime.strptime(published, "%Y-%m-%dT%H:%M:%SZ")
                if abs((now - pub_time).total_seconds() / 60) <= 5:
                    return True
    except: pass
    return False

def get_recent_candles(pair, count=1):
    url = f"https://api.taapi.io/candles?secret=demo&exchange=fx_idc&symbol={pair}&interval=1m&limit={count}"
    try:
        data = requests.get(url).json()
        return data.get("candles", [])
    except:
        return []

def detect_snr_from_history(candles):
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    return max(highs[-20:]), min(lows[-20:])

# === Analyzer ===
def analyze(pair):
    try:
        handler = TA_Handler(symbol=pair, screener="forex", exchange="FX_IDC", interval=Interval.INTERVAL_1_MINUTE)
        a = handler.get_analysis()
        i = a.indicators

        ema9, ema21 = i.get("EMA9", 0), i.get("EMA21", 0)
        rsi = i.get("RSI", 50)
        macd, macd_signal = i.get("MACD.macd", 0), i.get("MACD.signal", 0)
        open_, close, high, low = i.get("open", 0), i.get("close", 0), i.get("high", 0), i.get("low", 0)

        body = abs(close - open_)
        upper_wick = high - max(open_, close)
        lower_wick = min(open_, close) - low
        color = "green" if close > open_ else "red"

        direction = "UP" if ema9 > ema21 else "DOWN"
        confidence = "LOW"
        score = 0
        reasons = []

        if ema9 > ema21: reasons.append("EMA Up")
        if ema9 < ema21: reasons.append("EMA Down")
        if rsi < 30 and direction == "UP": score += 1; reasons.append("RSI Oversold")
        if rsi > 70 and direction == "DOWN": score += 1; reasons.append("RSI Overbought")
        if macd > macd_signal and direction == "UP": score += 1; reasons.append("MACD Bullish")
        if macd < macd_signal and direction == "DOWN": score += 1; reasons.append("MACD Bearish")
        if direction == "UP" and lower_wick > body: score += 1; reasons.append("Wick Reject")
        if direction == "DOWN" and upper_wick > body: score += 1; reasons.append("Wick Reject")
        if body > upper_wick + lower_wick: score += 1; reasons.append("Strong Body")

        candles = get_recent_candles(pair.replace("/", ""), 100)
        if candles:
            res, sup = detect_snr_from_history(candles)
            if direction == "UP" and close > sup: score += 1; reasons.append("Support Zone")
            if direction == "DOWN" and close < res: score += 1; reasons.append("Resistance Zone")

        if score >= 5: confidence = "HIGH"
        elif score >= 3: confidence = "MEDIUM"
        return direction, confidence, color, reasons
    except:
        return "UP", "LOW", "red", ["Fallback"]

# === Telegram Bot ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Start Signal", callback_data="start")]]
    await update.message.reply_text("👋 Welcome to Quotex Sniper", reply_markup=InlineKeyboardMarkup(keyboard))

async def pair_selector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    keyboard = [[InlineKeyboardButton(pair, callback_data=f"pair_{pair}")] for pair in PAIRS]
    await query.edit_message_text("📊 Choose a pair:", reply_markup=InlineKeyboardMarkup(keyboard))

async def send_signal(pair, user_id, context, is_retry=False):
    await context.bot.send_message(chat_id=user_id, text=f"📍 PAIR: {pair}
⏱️ TIME: 1 Minute
⏳ Waiting for candle...")
    current_minute = get_current_time().minute
    while get_current_time().minute == current_minute:
        await asyncio.sleep(0.5)

    if is_red_news():
        await context.bot.send_message(chat_id=user_id, text="🔕 Red news active. Trade skipped.")
        return

    direction, confidence, entry_color, reasons = analyze(pair)
    trade_id = len(trade_history) + 1
    trade_history.append({"id": trade_id, "pair": pair, "dir": direction, "conf": confidence, "entry_color": entry_color, "result": "WAIT", "retry": is_retry})

    total = len(trade_history)
    wins = len([x for x in trade_history if x["result"] == "WIN"])
    accuracy = round((wins / total) * 100, 2) if total else 0
    await context.bot.send_message(chat_id=user_id, text=f"📊 PAIR: {pair}
⏱️ TIME: 1m
🎯 Direction: {direction}
📌 Confidence: {confidence}
📊 Accuracy: {accuracy}%
💡 Logic: {' + '.join(reasons)}
Trade #{trade_id}")

    await asyncio.sleep(60)
    last_candle = get_recent_candles(pair.replace("/", ""), 1)
    if last_candle:
        candle = last_candle[0]
        open_, close = candle["open"], candle["close"]
        result = "WIN" if (direction == "UP" and close > open_) or (direction == "DOWN" and close < open_) else "LOSS"
        trade_history[-1]["result"] = result
        await context.bot.send_message(chat_id=user_id, text=f"🏁 RESULT: {result} for Trade #{trade_id}")

        if result == "LOSS" and confidence == "HIGH" and not is_retry:
            redir, _, _, _ = analyze(pair)
            if redir == direction:
                await context.bot.send_message(chat_id=user_id, text="🔁 Smart Retry Triggered")
                await send_signal(pair, user_id, context, is_retry=True)

    if trade_id % 3 == 0:
        await display_stats(user_id, context)

    keyboard = [[InlineKeyboardButton("🔁 Next Signal", callback_data=f"next_{pair}")]]
    await context.bot.send_message(chat_id=user_id, text="What’s next:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    pair = query.data.split("_")[1]
    await send_signal(pair, query.from_user.id, context)

async def handle_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    pair = query.data.split("_")[1]
    await send_signal(pair, query.from_user.id, context)

async def display_stats(user_id, context):
    total = len(trade_history)
    wins = len([x for x in trade_history if x["result"] == "WIN"])
    losses = len([x for x in trade_history if x["result"] == "LOSS"])
    rate = round((wins / total) * 100, 2) if total else 0
    last = trade_history[-1] if trade_history else {}
    msg = f"📊 Sniper Bot Stats:
✅ Wins: {wins}
❌ Losses: {losses}
🎯 Accuracy: {rate}%"
    if last:
        msg += f"
🆔 Last: #{last['id']} {last['pair']} | {last['dir']} | {last['conf']} | {last['result']}"
    await context.bot.send_message(chat_id=user_id, text=msg)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await display_stats(update.message.chat_id, context)

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "📋 Trade History:
"
    for t in trade_history[-10:]:
        retry = " (Retry)" if t.get("retry") else ""
        msg += f"#{t['id']} {t['pair']} | {t['dir']} | {t['conf']}{retry} | {t['result']}
"
    await update.message.reply_text(msg or "No trades yet.")

# === Main ===
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CallbackQueryHandler(pair_selector, pattern="^start$"))
    app.add_handler(CallbackQueryHandler(handle_pair, pattern="^pair_"))
    app.add_handler(CallbackQueryHandler(handle_next, pattern="^next_"))
    print("✅ Sniper Bot with Candle Win Detection + Live Stats is Running")
    app.run_polling()
