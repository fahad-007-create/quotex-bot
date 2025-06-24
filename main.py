# Real Quotex Signal Bot (v1)
import requests, time, datetime
from tradingview_ta import TA_Handler, Interval
import pytz

# === CONFIG ===
TELEGRAM_TOKEN = "7704084377:AAG56RXCZvJpnTlTEMSKO9epJUl9B8-1on8"
TELEGRAM_CHAT_ID = "6183147124"
NEWS_API_KEY = "8b5c91784c144924a179b7b0899ba61f"

PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD",
    "NZDUSD", "USDCAD", "EURJPY", "GBPJPY", "EURGBP", "EURCHF"
]

INTERVALS = {
    "1m": Interval.INTERVAL_1_HOUR,
    "5m": Interval.INTERVAL_1_HOUR
}

def get_news_status():
    try:
        url = f"https://newsapi.org/v2/top-headlines?category=business&language=en&apiKey={NEWS_API_KEY}"
        res = requests.get(url).json()
        if 'articles' in res and len(res['articles']) > 0:
            return True
    except:
        return False
    return False

def get_pk_time():
    return datetime.datetime.now(pytz.timezone("Asia/Karachi"))

def is_in_trading_session():
    now = get_pk_time()
    total_minutes = now.hour * 60 + now.minute
    return (720 <= total_minutes <= 990) or (1080 <= total_minutes <= 1320)

def send_signal(pair, tf, signal, confidence, reason):
    tag = "✅ Real Market Signal" if reason != "NEWS" else "⚠️ News Signal"
    msg = f"""
📊 PAIR: {pair}
⏱️ TIMEFRAME: {tf}
🎯 CONFIDENCE: {confidence}
📈 DIRECTION: {signal.upper()}
🧠 STRATEGY: {tag}
    """.strip()
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
    response = requests.post(url, data=data)
    print("📤 Sent signal:", msg)
    return response

def get_signal(pair, tf):
    try:
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

        print(f"✅ Checked {pair} {tf}: Direction={direction}, Confidence={confidence}")
        return direction, confidence
    except Exception as e:
        print(f"❌ Error analyzing {pair} {tf}:", e)
        return "WAIT", "LOW"

# === MAIN LOOP ===
if __name__ == "__main__":
    while True:
        if not is_in_trading_session():
            print(f"⏳ Waiting for trading session... ({get_pk_time().strftime('%H:%M')})")
            time.sleep(60)
            continue

        is_news = get_news_status()
        for pair in PAIRS:
            for tf in ["1m", "5m"]:
                direction, confidence = get_signal(pair, tf)
                if direction != "WAIT":
                    source = "NEWS" if is_news else "MARKET"
                    send_signal(pair, tf.upper(), direction, confidence, source)
        time.sleep(60)
