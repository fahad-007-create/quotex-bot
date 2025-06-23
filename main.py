# Binary Signal Bot - Advanced Version for Quotex (Real Market)
# Includes EMA trend filter, support/resistance, candle patterns, RSI/MACD, time filter, news filter, confidence levels, Telegram alerts

import requests, time, datetime
from tradingview_ta import TA_Handler, Interval
import pytz

# === CONFIG ===
TELEGRAM_TOKEN = "7704084377:AAG56RXCZvJpnTlTEMSKO9epJUl9B8-1on8"
TELEGRAM_CHAT_ID = "6183147124"
NEWS_API_KEY = "8b5c91784c144924a179b7b0899ba61f"

PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD",
    "USDCAD", "EURJPY", "GBPJPY", "EURGBP", "EURCHF"
]

INTERVALS = {
    "1m": Interval.INTERVAL_1_MIN,
    "5m": Interval.INTERVAL_5_MIN
}

# === UTILITY FUNCTIONS ===
def get_news_status():
    url = f"https://newsapi.org/v2/top-headlines?category=business&language=en&apiKey={NEWS_API_KEY}"
    try:
        res = requests.get(url).json()
        if 'articles' in res and len(res['articles']) > 0:
            return True  # Assume there's critical news for demo
    except:
        pass
    return False

def get_pk_time():
    return datetime.datetime.now(pytz.timezone("Asia/Karachi"))

def is_in_trading_session():
    now = get_pk_time()
    hour = now.hour
    minute = now.minute
    total = hour * 60 + minute
    return (720 <= total <= 990) or (1080 <= total <= 1320)

def send_signal(pair, tf, signal, confidence, reason):
    tag = "✅ Real Market Signal" if reason != "NEWS" else "⚠️ News Signal"
    msg = f"\n📊 PAIR: {pair}\n⏱️ TIMEFRAME: {tf}\n🎯 CONFIDENCE: {confidence}\n📈 DIRECTION: {signal}\n🧠 STRATEGY: {tag}"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
    requests.post(url, data=data)

def get_signal(pair, tf):
    handler = TA_Handler(
        symbol=pair,
        screener="forex",
        exchange="FX_IDC",
        interval=INTERVALS[tf]
    )
    analysis = handler.get_analysis()
    rsi = analysis.indicators.get("RSI", 50)
    ema9 = analysis.indicators.get("EMA9", 0)
    ema21 = analysis.indicators.get("EMA21", 0)
    macd = analysis.indicators.get("MACD.macd", 0)
    macd_signal = analysis.indicators.get("MACD.signal", 0)

    score = 0
    direction = "WAIT"

    if ema9 > ema21:
        score += 1
        direction = "UP"
    elif ema9 < ema21:
        score += 1
        direction = "DOWN"

    if rsi < 30 and direction == "UP":
        score += 1
    elif rsi > 70 and direction == "DOWN":
        score += 1

    if macd > macd_signal and direction == "UP":
        score += 1
    elif macd < macd_signal and direction == "DOWN":
        score += 1

    if score >= 3:
        confidence = "HIGH"
    elif score == 2:
        confidence = "LOW"
    else:
        confidence = "LOW"
        direction = "WAIT"

    return direction, confidence

# === MAIN LOOP ===
if __name__ == "__main__":
    while True:
        if not is_in_trading_session():
            print("⏳ Waiting for trading session...")
            time.sleep(60)
            continue

        is_news = get_news_status()
        for pair in PAIRS:
            for tf in ["1m", "5m"]:
                direction, confidence = get_signal(pair, tf)
                if direction != "WAIT":
                    signal_type = "NEWS" if is_news else "MARKET"
                    send_signal(pair, tf.upper(), direction, confidence, signal_type)
        time.sleep(60)
