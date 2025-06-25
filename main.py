# main.py
import json
import time
import logging
import requests
from flask import Flask, request
from config import TELEGRAM_TOKEN, CHAT_ID, PAIRS

app = Flask(__name__)

# Initialize stats
stats = {
    "wins": 0,
    "losses": 0,
    "total": 0
}

# Store last signal to handle "Next Signal" logic
last_pair = None
last_direction = None
awaiting_result = False

# Send Telegram message
def send_telegram_message(text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    requests.post(url, data=payload)

# Analyze candle and decide signal
def analyze_candle(data):
    open_price = float(data["open"])
    close_price = float(data["close"])
    high = float(data["high"])
    low = float(data["low"])
    
    candle_body = abs(close_price - open_price)
    wick_top = high - max(open_price, close_price)
    wick_bottom = min(open_price, close_price) - low

    # Simple bullish engulfing + rejection logic
    if close_price > open_price and wick_bottom > wick_top:
        return "BUY"
    elif close_price < open_price and wick_top > wick_bottom:
        return "SELL"
    else:
        return None

@app.route("/webhook", methods=["POST"])
def webhook():
    global last_pair, last_direction, awaiting_result
    data = request.json
    print(f"Received data: {data}")

    pair = data.get("pair")
    timeframe = data.get("timeframe")
    
    if pair not in PAIRS or timeframe != "1m":
        return "Ignored", 200

    signal = analyze_candle(data)
    if signal:
        last_pair = pair
        last_direction = signal
        awaiting_result = True

        msg = f"\ud83d\udd25 <b>Binary Signal</b>\n\ud83d\udccb Pair: <b>{pair}</b>\n\u23f0 Timeframe: <b>1 Minute</b>\n\ud83d\udfe2 Direction: <b>{signal}</b>\n\ud83d\udccd Reason: Rejection Wick + Candle Body\n\n<b>Click below for next signal \u2b07\ufe0f</b>"
        send_telegram_message(msg, reply_markup={
            "inline_keyboard": [[
                {"text": "➡️ Next Signal", "callback_data": "next_signal"}
            ]]
        })
    return "OK", 200

@app.route("/callback", methods=["POST"])
def callback():
    global last_pair, last_direction, awaiting_result
    query = request.json
    if query["data"] == "next_signal":
        if last_pair:
            # Wait for next candle close in real setup
            # For now simulate next signal
            time.sleep(2)  # Simulated delay
            send_telegram_message(f"Next signal on <b>{last_pair}</b> coming shortly...")
    return "OK", 200

@app.route("/stats", methods=["GET"])
def stat():
    acc = (stats["wins"] / stats["total"] * 100) if stats["total"] > 0 else 0
    text = f"\ud83d\udcca Bot Stats:\n✅ Wins: {stats['wins']}\n❌ Losses: {stats['losses']}\n🔁 Total: {stats['total']}\n🎯 Accuracy: {acc:.2f}%"
    send_telegram_message(text)
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
