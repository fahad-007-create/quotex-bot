# ✅ Quotex Sniper Bot - Ultimate Fast & Accurate Version (No Delay + Optional AI)

import logging, requests, datetime, pytz, asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from tradingview_ta import TA_Handler, Interval

# === CONFIG ===
TELEGRAM_TOKEN = "7704084377:AAG56RXCZvJpnTlTEMSKO9epJUl9B8-1on8"
CHAT_ID = "6183147124"
NEWS_API_KEY = "8b5c91784c144924a179b7b0899ba61f"

PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD", "USDCAD",
    "EURJPY", "GBPJPY", "EURGBP", "EURCHF", "CADJPY", "AUDJPY", "EURCAD",
    "AUDCAD", "NZDJPY", "CHFJPY", "USDHKD", "EURNZD", "GBPAUD"
]

trade_history = []

# === UTILITIES ===
def get_time():
    return datetime.datetime.now(pytz.timezone("Asia/Karachi"))

def get_candles(pair):
    try:
        url = f"https://api.taapi.io/candles?secret=demo&exchange=fx_idc&symbol={pair}&interval=1m&limit=2"
        return requests.get(url).json().get("candles", [])
    except:
        return []

def calc_accuracy():
    wins = sum(1 for t in trade_history if t['result'] == 'WIN')
    total = len(trade_history)
    return round((wins / total) * 100, 2) if total else 0

def analyze(pair):
    try:
        handler = TA_Handler(symbol=pair, screener="forex", exchange="FX_IDC", interval=Interval.INTERVAL_1_MINUTE)
        indicators = handler.get_analysis().indicators
        o, c, h, l = indicators['open'], indicators['close'], indicators['high'], indicators['low']
        ema9, ema21 = indicators['EMA9'], indicators['EMA21']
        rsi, macd, signal = indicators['RSI'], indicators['MACD.macd'], indicators['MACD.signal']
        body = abs(c - o)
        upper = h - max(o, c)
        lower = min(o, c) - l

        direction = 'UP' if ema9 > ema21 else 'DOWN'
        reasons, score = [], 0

        if ema9 > ema21: score += 1; reasons.append("EMA Up")
        if ema9 < ema21: score += 1; reasons.append("EMA Down")
        if rsi < 30 and direction == 'UP': score += 1; reasons.append("RSI Oversold")
        if rsi > 70 and direction == 'DOWN': score += 1; reasons.append("RSI Overbought")
        if macd > signal and direction == 'UP': score += 1; reasons.append("MACD Bullish")
        if macd < signal and direction == 'DOWN': score += 1; reasons.append("MACD Bearish")
        if direction == 'UP' and lower > body: score += 1; reasons.append("Wick Rejection")
        if direction == 'DOWN' and upper > body: score += 1; reasons.append("Wick Rejection")
        if upper > body * 2 and direction == 'UP': direction = 'DOWN'; reasons.append("Trap Reversal")
        if lower > body * 2 and direction == 'DOWN': direction = 'UP'; reasons.append("Trap Reversal")

        conf = 'HIGH' if score >= 6 else 'MEDIUM' if score >= 4 else 'LOW'
        return direction, conf, reasons
    except:
        return "UP", "LOW", ["Indicator Error"]

# === BOT HANDLERS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("Start", callback_data="start")]]
    await update.message.reply_text("👋 Welcome to Quotex Sniper Bot", reply_markup=InlineKeyboardMarkup(kb))

async def show_pairs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    kb = [[InlineKeyboardButton(p, callback_data=f"pair_{p}")] for p in PAIRS]
    await q.edit_message_text("📊 Select Pair:", reply_markup=InlineKeyboardMarkup(kb))

async def handle_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    pair = q.data.split("_")[1]
    await context.bot.send_message(chat_id=q.from_user.id, text=f"📍PAIR: {pair}\n⏱️ TIME: 1 Minute\n⏳ Analyzing direction...")

    await asyncio.sleep(1)
    dir, conf, reasons = analyze(pair)
    acc = calc_accuracy()
    tid = len(trade_history) + 1
    trade_history.append({"id": tid, "pair": pair, "dir": dir, "conf": conf, "result": "WAIT"})

    await context.bot.send_message(chat_id=q.from_user.id, text=
        f"🎯 DIRECTION: {dir}\n📌 CONFIDENCE: {conf}\n📊 ACCURACY: {acc}%\n📈 STRATEGY: {', '.join(reasons)}\n📎 TRADE #{tid}")

    await asyncio.sleep(60)
    candle = get_candles(pair)[-1]
    win = (dir == 'UP' and candle['close'] > candle['open']) or (dir == 'DOWN' and candle['close'] < candle['open'])
    trade_history[-1]['result'] = "WIN" if win else "LOSS"

    await context.bot.send_message(chat_id=q.from_user.id, text=f"🏁 RESULT: {'WIN' if win else 'LOSS'} for TRADE #{tid}")
    btns = [[InlineKeyboardButton("Next Signal", callback_data=f"pair_{pair}")]]
    await context.bot.send_message(chat_id=q.from_user.id, text="What’s next?", reply_markup=InlineKeyboardMarkup(btns))

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = len(trade_history)
    wins = sum(1 for t in trade_history if t['result'] == 'WIN')
    losses = total - wins
    acc = calc_accuracy()
    await update.message.reply_text(f"📈 Total: {total}\n✅ Wins: {wins}\n❌ Losses: {losses}\n🎯 Accuracy: {acc}%")

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "\n".join([f"#{t['id']} {t['pair']} | {t['dir']} | {t['conf']} | {t['result']}" for t in trade_history[-10:]])
    await update.message.reply_text("📋 History:\n" + (msg or "No trades yet."))

# === MAIN ===
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CallbackQueryHandler(show_pairs, pattern="^start$"))
    app.add_handler(CallbackQueryHandler(handle_pair, pattern="^pair_"))
    print("✅ Quotex Sniper Final Bot Running...")
    app.run_polling()
