# ✅ Quotex Sniper Bot - Full Version with Candle Logic + Accuracy % + Smart Retry

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

trade_history = []

def get_time():
    return datetime.datetime.now(pytz.timezone("Asia/Karachi"))

def is_red_news():
    try:
        res = requests.get(f"https://newsapi.org/v2/top-headlines?category=business&language=en&apiKey={NEWS_API_KEY}").json()
        articles = res.get("articles", [])
        now = datetime.datetime.utcnow()
        for a in articles:
            if 'publishedAt' in a:
                pub = datetime.datetime.strptime(a['publishedAt'], "%Y-%m-%dT%H:%M:%SZ")
                if abs((now - pub).total_seconds()) <= 300:
                    return True
    except: pass
    return False

def get_candles(pair, count=1):
    url = f"https://api.taapi.io/candles?secret=demo&exchange=fx_idc&symbol={pair}&interval=1m&limit={count}"
    try:
        return requests.get(url).json().get("candles", [])
    except:
        return []

def detect_snr(candles):
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    return max(highs[-20:]), min(lows[-20:])

def analyze(pair):
    try:
        handler = TA_Handler(symbol=pair, screener="forex", exchange="FX_IDC", interval=Interval.INTERVAL_1_MINUTE)
        a = handler.get_analysis()
        i = a.indicators
        ema9, ema21 = i["EMA9"], i["EMA21"]
        rsi, macd, macd_signal = i["RSI"], i["MACD.macd"], i["MACD.signal"]
        open_, close = i["open"], i["close"]
        high, low = i["high"], i["low"]

        body = abs(close - open_)
        upper = high - max(open_, close)
        lower = min(open_, close) - low
        color = "green" if close > open_ else "red"
        direction = "UP" if ema9 > ema21 else "DOWN"
        score = 0
        reasons = []

        if rsi < 30 and direction == "UP": score += 1; reasons.append("RSI Oversold")
        if rsi > 70 and direction == "DOWN": score += 1; reasons.append("RSI Overbought")
        if macd > macd_signal and direction == "UP": score += 1; reasons.append("MACD Bullish")
        if macd < macd_signal and direction == "DOWN": score += 1; reasons.append("MACD Bearish")
        if direction == "UP" and lower > body: score += 1; reasons.append("Rejection Wick")
        if direction == "DOWN" and upper > body: score += 1; reasons.append("Rejection Wick")

        candles = get_candles(pair, 100)
        if candles:
            res, sup = detect_snr(candles)
            if direction == "UP" and close > sup: score += 1; reasons.append("Support Zone")
            if direction == "DOWN" and close < res: score += 1; reasons.append("Resistance Zone")

        confidence = "HIGH" if score >= 4 else "MEDIUM" if score == 3 else "LOW"
        return direction, confidence, color, reasons
    except:
        return "UP", "LOW", "red", ["Fallback"]

async def send_signal(pair, user_id, context, retry=False):
    await context.bot.send_message(chat_id=user_id, text=f"📍 PAIR: {pair}\n⏱️ TIME: 1 Minute\n⏳ Waiting for next candle...")
    curr = get_time().minute
    while get_time().minute == curr:
        await asyncio.sleep(0.5)

    if is_red_news():
        await context.bot.send_message(chat_id=user_id, text="🔕 Red News Active. Skipped.")
        return

    direction, confidence, entry_color, reasons = analyze(pair)
    trade_id = len(trade_history) + 1
    trade_history.append({"id": trade_id, "pair": pair, "dir": direction, "conf": confidence, "entry_color": entry_color, "result": "WAIT", "retry": retry})

    wins = len([t for t in trade_history if t["result"] == "WIN"])
    total = len(trade_history)
    accuracy = round((wins / total) * 100, 2) if total else 0

    await context.bot.send_message(
        chat_id=user_id,
        text=f"📊 PAIR: {pair}\n⏱️ TIME: 1m\n🎯 Direction: {direction}\n📌 Confidence: {confidence}\n📊 Accuracy: {accuracy}%\n💡 Logic: {' + '.join(reasons)}\nTrade #{trade_id}"
    )

    await asyncio.sleep(60)
    candle = get_candles(pair, 1)[0]
    result = "WIN" if (direction == "UP" and candle["close"] > candle["open"]) or (direction == "DOWN" and candle["close"] < candle["open"]) else "LOSS"
    trade_history[-1]["result"] = result
    await context.bot.send_message(chat_id=user_id, text=f"🏁 RESULT: {result} for Trade #{trade_id}")

    if result == "LOSS" and confidence == "HIGH" and not retry:
        redir, _, _, _ = analyze(pair)
        if redir == direction:
            await context.bot.send_message(chat_id=user_id, text="🔁 Retrying same direction...")
            await send_signal(pair, user_id, context, retry=True)

    if trade_id % 3 == 0:
        await display_stats(user_id, context)

    keyboard = [[InlineKeyboardButton("🔁 Next Signal", callback_data=f"next_{pair}")]]
    await context.bot.send_message(chat_id=user_id, text="Ready for next signal?", reply_markup=InlineKeyboardMarkup(keyboard))

# === Telegram Bot ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("Start Signal", callback_data="start")]]
    await update.message.reply_text("👋 Welcome to Quotex Bot", reply_markup=InlineKeyboardMarkup(kb))

async def select_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    kb = [[InlineKeyboardButton(pair, callback_data=f"pair_{pair}")] for pair in PAIRS]
    await query.edit_message_text("📊 Choose a pair:", reply_markup=InlineKeyboardMarkup(kb))

async def handle_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pair = update.callback_query.data.split("_")[1]
    await send_signal(pair, update.callback_query.from_user.id, context)

async def handle_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pair = update.callback_query.data.split("_")[1]
    await send_signal(pair, update.callback_query.from_user.id, context)

async def display_stats(user_id, context):
    total = len(trade_history)
    wins = len([t for t in trade_history if t["result"] == "WIN"])
    losses = len([t for t in trade_history if t["result"] == "LOSS"])
    rate = round((wins / total) * 100, 2) if total else 0
    last = trade_history[-1]
    msg = f"📊 Stats:\n✅ Wins: {wins}\n❌ Losses: {losses}\n🎯 Accuracy: {rate}%\n🆔 Last: #{last['id']} {last['pair']} | {last['dir']} | {last['conf']} | {last['result']}"
    await context.bot.send_message(chat_id=user_id, text=msg)

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "📋 History:\n"
    for t in trade_history[-10:]:
        retry = " (Retry)" if t.get("retry") else ""
        msg += f"#{t['id']} {t['pair']} | {t['dir']} | {t['conf']}{retry} | {t['result']}\n"
    await update.message.reply_text(msg or "No trades yet.")

# === Bot Runner ===
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CallbackQueryHandler(select_pair, pattern="^start$"))
    app.add_handler(CallbackQueryHandler(handle_pair, pattern="^pair_"))
    app.add_handler(CallbackQueryHandler(handle_next, pattern="^next_"))
    print("✅ Sniper Bot running...")
    app.run_polling()
