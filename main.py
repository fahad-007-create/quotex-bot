# ✅ Quotex Sniper Bot - Ultimate AI-Enhanced Version (by Fahad & ChatGPT)

import logging
import requests
import datetime
import pytz
import asyncio
import os
from dotenv import load_dotenv
import openai

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from tradingview_ta import TA_Handler, Interval

# === Load .env variables FIRST ===
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# === CONFIG ===
TELEGRAM_TOKEN = "7704084377:AAG56RXCZvJpnTlTEMSKO9epJUl9B8-1on8"
CHAT_ID = "6183147124"
NEWS_API_KEY = "8b5c91784c144924a179b7b0899ba61f"

PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD", "USDCAD",
    "EURJPY", "GBPJPY", "EURGBP", "EURCHF", "CADJPY", "AUDJPY", "EURCAD",
    "AUDCAD", "NZDJPY", "CHFJPY", "USDHKD", "EURNZD", "GBPAUD"
]

user_selection = {}
trade_history = []

# === UTILITIES ===
def get_time():
    return datetime.datetime.now(pytz.timezone("Asia/Karachi"))

def in_killzone():
    now = get_time()
    m = now.hour * 60 + now.minute
    return (690 <= m <= 810) or (1080 <= m <= 1200)  # 11:30–13:30 & 18:00–20:00 PKT

def is_red_news():
    try:
        r = requests.get(f"https://newsapi.org/v2/top-headlines?category=business&language=en&apiKey={NEWS_API_KEY}").json()
        for a in r.get("articles", []):
            t = datetime.datetime.strptime(a.get("publishedAt"), "%Y-%m-%dT%H:%M:%SZ")
            if abs((datetime.datetime.utcnow() - t).total_seconds()) <= 300:
                return True
    except: pass
    return False

def get_candles(pair, count=100):
    url = f"https://api.taapi.io/candles?secret=demo&exchange=fx_idc&symbol={pair}&interval=1m&limit={count}"
    try:
        return requests.get(url).json().get("candles", [])
    except: return []

def calc_accuracy():
    w = sum(1 for t in trade_history if t['result'] == 'WIN')
    return round((w / len(trade_history)) * 100, 2) if trade_history else 0

# === STRATEGY ANALYSIS ===
def analyze(pair):
    handler = TA_Handler(symbol=pair, screener="forex", exchange="FX_IDC", interval=Interval.INTERVAL_1_MINUTE)
    i = handler.get_analysis().indicators
    o, c, h, l = i['open'], i['close'], i['high'], i['low']
    ema9, ema21 = i['EMA9'], i['EMA21']
    rsi, macd, macdsig = i['RSI'], i['MACD.macd'], i['MACD.signal']
    
    body = abs(c - o)
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l
    color = 'green' if c > o else 'red'
    
    direction = 'UP' if ema9 > ema21 else 'DOWN'
    reasons, score = [], 0

    if ema9 > ema21: reasons.append("EMA Up"); score += 1
    if ema9 < ema21: reasons.append("EMA Down"); score += 1
    if direction == 'UP' and rsi < 30: reasons.append("RSI Oversold"); score += 1
    if direction == 'DOWN' and rsi > 70: reasons.append("RSI Overbought"); score += 1
    if direction == 'UP' and macd > macdsig: reasons.append("MACD Bullish"); score += 1
    if direction == 'DOWN' and macd < macdsig: reasons.append("MACD Bearish"); score += 1
    if direction == 'UP' and lower_wick > body: reasons.append("Wick Rejection"); score += 1
    if direction == 'DOWN' and upper_wick > body: reasons.append("Wick Rejection"); score += 1

    # Trap Wick Logic
    if upper_wick > body * 2 and direction == 'UP': reasons.append("Trap Reversal"); direction = 'DOWN'
    if lower_wick > body * 2 and direction == 'DOWN': reasons.append("Trap Reversal"); direction = 'UP'

    if body > upper_wick + lower_wick: reasons.append("Strong Body"); score += 1

    conf = 'LOW'
    if score >= 6: conf = 'HIGH'
    elif score >= 4: conf = 'MEDIUM'

    return direction, conf, color, reasons

# === CHATGPT COMMENTARY ===
def get_explanation(pair, reasons, direction):
    try:
        prompt = f"Explain the following forex signal in simple language:\nPair: {pair}\nDirection: {direction}\nReasons: {', '.join(reasons)}"
        res = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}])
        return res['choices'][0]['message']['content']
    except:
        return "💡 Signal based on: " + ', '.join(reasons)

# === TELEGRAM HANDLERS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("Start", callback_data="start")]]
    await update.message.reply_text("👋 Welcome to AI Sniper Bot", reply_markup=InlineKeyboardMarkup(kb))

async def pair_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    kb = [[InlineKeyboardButton(p, callback_data=f"pair_{p}")] for p in PAIRS]
    await query.edit_message_text("📊 Select Pair:", reply_markup=InlineKeyboardMarkup(kb))

async def handle_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    pair = q.data.split("_")[1]
    now = get_time()
    while now.second > 2: await asyncio.sleep(0.5); now = get_time()
    if not in_killzone(): await context.bot.send_message(chat_id=q.from_user.id, text="🕒 Not killzone time."); return
    if is_red_news(): await context.bot.send_message(chat_id=q.from_user.id, text="🔕 Red news active. Skipping."); return

    dir, conf, col, reasons = analyze(pair)
    tid = len(trade_history) + 1
    trade_history.append({"id": tid, "pair": pair, "dir": dir, "conf": conf, "result": "WAIT", "entry_col": col})
    acc = calc_accuracy()
    explanation = get_explanation(pair, reasons, dir)
    
    msg = f"📊 PAIR: {pair}\n⏱️ TIME: 1 Minute\n🎯 Direction: {dir}\n📌 Confidence: {conf}\n📊 Accuracy: {acc}%\n🧠 {explanation}\n📎 Trade #{tid}"
    await context.bot.send_message(chat_id=q.from_user.id, text=msg)

    await asyncio.sleep(60)
    cndl = get_candles(pair.replace("/", ""), 1)[0]
    res = "WIN" if (dir == "UP" and cndl['close'] > cndl['open']) or (dir == "DOWN" and cndl['close'] < cndl['open']) else "LOSS"
    trade_history[-1]['result'] = res
    await context.bot.send_message(chat_id=q.from_user.id, text=f"🏁 RESULT: {res} for Trade #{tid}")

    kb = [[InlineKeyboardButton("Next Signal", callback_data=f"pair_{pair}")]]
    await context.bot.send_message(chat_id=q.from_user.id, text="What’s next:", reply_markup=InlineKeyboardMarkup(kb))

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = len(trade_history)
    wins = len([x for x in trade_history if x['result'] == 'WIN'])
    losses = len([x for x in trade_history if x['result'] == 'LOSS'])
    acc = calc_accuracy()
    msg = f"📈 Stats:\nTotal: {total}\n✅ Wins: {wins}\n❌ Losses: {losses}\n🎯 Accuracy: {acc}%"
    await update.message.reply_text(msg)

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "📋 Trade History:\n"
    for t in trade_history[-10:]:
        msg += f"#{t['id']} {t['pair']} | {t['dir']} | {t['conf']} | {t['result']}\n"
    await update.message.reply_text(msg or "No trades yet.")

# === MAIN ===
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CallbackQueryHandler(pair_handler, pattern="^start$"))
    app.add_handler(CallbackQueryHandler(handle_pair, pattern="^pair_"))
    print("✅ Quotex Sniper AI Bot is Running...")
    app.run_polling()
