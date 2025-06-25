# ✅ Quotex Sniper Bot - AI Enhanced + 24/7 Working

import logging, requests, datetime, pytz, asyncio, openai
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from tradingview_ta import TA_Handler, Interval

# === CONFIG ===
TELEGRAM_TOKEN = "7704084377:AAG56RXCZvJpnTlTEMSKO9epJUl9B8-1on8"
CHAT_ID = "6183147124"
NEWS_API_KEY = "8b5c91784c144924a179b7b0899ba61f"
OPENAI_API_KEY = "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"
openai.api_key = OPENAI_API_KEY

PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD", "USDCAD",
         "EURJPY", "GBPJPY", "EURGBP", "EURCHF", "CADJPY", "AUDJPY", "EURCAD",
         "AUDCAD", "NZDJPY", "CHFJPY", "USDHKD", "EURNZD", "GBPAUD"]

trade_history = []

def get_time():
    return datetime.datetime.now(pytz.timezone("Asia/Karachi"))

def is_red_news():
    try:
        r = requests.get(f"https://newsapi.org/v2/top-headlines?category=business&language=en&apiKey={NEWS_API_KEY}").json()
        for a in r.get("articles", []):
            t = datetime.datetime.strptime(a.get("publishedAt"), "%Y-%m-%dT%H:%M:%SZ")
            if abs((datetime.datetime.utcnow() - t).total_seconds()) <= 300:
                return True
    except: return False

def get_candles(pair, count=1):
    url = f"https://api.taapi.io/candles?secret=demo&exchange=fx_idc&symbol={pair}&interval=1m&limit={count}"
    try: return requests.get(url).json().get("candles", [])
    except: return []

def calc_accuracy():
    total = len(trade_history)
    win = sum(1 for t in trade_history if t['result'] == 'WIN')
    return round((win / total) * 100, 2) if total else 0

def analyze(pair):
    handler = TA_Handler(symbol=pair, screener="forex", exchange="FX_IDC", interval=Interval.INTERVAL_1_MINUTE)
    i = handler.get_analysis().indicators
    o, c, h, l = i['open'], i['close'], i['high'], i['low']
    ema9, ema21 = i['EMA9'], i['EMA21']
    rsi, macd, macdsig = i['RSI'], i['MACD.macd'], i['MACD.signal']
    body = abs(c - o)
    upper = h - max(o, c)
    lower = min(o, c) - l
    color = 'green' if c > o else 'red'
    direction = 'UP' if ema9 > ema21 else 'DOWN'
    score, reasons = 0, []

    if ema9 > ema21: score += 1; reasons.append("EMA Up")
    if ema9 < ema21: score += 1; reasons.append("EMA Down")
    if rsi < 30 and direction == 'UP': score += 1; reasons.append("RSI Oversold")
    if rsi > 70 and direction == 'DOWN': score += 1; reasons.append("RSI Overbought")
    if macd > macdsig and direction == 'UP': score += 1; reasons.append("MACD Bullish")
    if macd < macdsig and direction == 'DOWN': score += 1; reasons.append("MACD Bearish")
    if direction == 'UP' and lower > body: score += 1; reasons.append("Wick Rejection")
    if direction == 'DOWN' and upper > body: score += 1; reasons.append("Wick Rejection")
    if upper > body * 2 and direction == 'UP': direction = 'DOWN'; reasons.append("Trap Reversal")
    if lower > body * 2 and direction == 'DOWN': direction = 'UP'; reasons.append("Trap Reversal")
    if body > upper + lower: score += 1; reasons.append("Strong Body")

    conf = 'HIGH' if score >= 6 else 'MEDIUM' if score >= 4 else 'LOW'
    return direction, conf, color, reasons

def get_explanation(pair, reasons, direction):
    try:
        prompt = f"Explain this forex signal:\nPair: {pair}\nDirection: {direction}\nReasons: {', '.join(reasons)}"
        res = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}])
        return res['choices'][0]['message']['content']
    except: return "🧠 " + ', '.join(reasons)

# === Bot Handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    btns = [[InlineKeyboardButton("Start Signal", callback_data="start")]]
    await update.message.reply_text("👋 Welcome to Quotex AI Bot", reply_markup=InlineKeyboardMarkup(btns))

async def show_pairs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    btns = [[InlineKeyboardButton(p, callback_data=f"pair_{p}")] for p in PAIRS]
    await q.edit_message_text("📊 Select a pair:", reply_markup=InlineKeyboardMarkup(btns))

async def handle_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    pair = q.data.split("_")[1]
    while get_time().second > 2: await asyncio.sleep(0.5)

    if is_red_news():
        await context.bot.send_message(chat_id=q.from_user.id, text="🚫 Red news detected. Skipping signal.")
        return

    dir, conf, color, reasons = analyze(pair)
    tid = len(trade_history) + 1
    trade_history.append({"id": tid, "pair": pair, "dir": dir, "conf": conf, "entry_col": color, "result": "WAIT"})
    acc = calc_accuracy()
    explanation = get_explanation(pair, reasons, dir)

    await context.bot.send_message(chat_id=q.from_user.id, text=
        f"📊 PAIR: {pair}\n⏱️ TIME: 1 Minute\n🎯 Direction: {dir}\n📌 Confidence: {conf}\n📊 Accuracy: {acc}%\n🧠 {explanation}\n📎 Trade #{tid}")

    await asyncio.sleep(60)
    cndl = get_candles(pair.replace("/", ""), 1)[0]
    win = (dir == "UP" and cndl["close"] > cndl["open"]) or (dir == "DOWN" and cndl["close"] < cndl["open"])
    result = "WIN" if win else "LOSS"
    trade_history[-1]["result"] = result

    await context.bot.send_message(chat_id=q.from_user.id, text=f"🏁 RESULT: {result} for Trade #{tid}")
    btns = [[InlineKeyboardButton("Next Signal", callback_data=f"pair_{pair}")]]
    await context.bot.send_message(chat_id=q.from_user.id, text="What’s next?", reply_markup=InlineKeyboardMarkup(btns))

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = len(trade_history)
    win = sum(1 for t in trade_history if t["result"] == "WIN")
    loss = sum(1 for t in trade_history if t["result"] == "LOSS")
    acc = calc_accuracy()
    await update.message.reply_text(f"📈 Total: {total}\n✅ Wins: {win}\n❌ Losses: {loss}\n🎯 Accuracy: {acc}%")

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "\n".join([f"#{t['id']} {t['pair']} | {t['dir']} | {t['conf']} | {t['result']}" for t in trade_history[-10:]])
    await update.message.reply_text("📋 History:\n" + (msg or "No trades yet."))

# === Main Runner ===
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CallbackQueryHandler(show_pairs, pattern="^start$"))
    app.add_handler(CallbackQueryHandler(handle_pair, pattern="^pair_"))
    print("✅ Quotex Sniper AI Bot is Running...")
    app.run_polling()
