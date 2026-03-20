import os
import requests
import asyncio
from telegram import Bot

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN environment variable is required")

bot = Bot(token=TELEGRAM_TOKEN)

CHAT_ID = None
symbols = ["BTCUSDT", "ETHUSDT"]
last_prices = {}

def safe_request(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception:
        return None

def get_price(symbol):
    data = safe_request(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}")
    if data and 'price' in data:
        return float(data['price'])
    return None

def get_trades(symbol):
    return safe_request(f"https://api.binance.com/api/v3/trades?symbol={symbol}&limit=20") or []

async def monitor():
    global CHAT_ID

    while True:
        try:
            for symbol in symbols:
                price = get_price(symbol)
                if not price:
                    continue

                trades = get_trades(symbol)

                # ===== 价格监控 =====
                if symbol in last_prices:
                    change = (price - last_prices[symbol]) / last_prices[symbol]

                    if abs(change) > 0.01 and CHAT_ID:
                        msg = f"{symbol} 变动 {round(change*100,2)}%\n价格: {price}"
                        await bot.send_message(chat_id=CHAT_ID, text=msg)

                last_prices[symbol] = price

                # ===== 大单检测 =====
                for trade in trades:
                    try:
                        qty = float(trade['qty'])
                        trade_price = float(trade['price'])
                        value = qty * trade_price

                        if value > 100000 and CHAT_ID:
                            side = "买入" if not trade['isBuyerMaker'] else "卖出"

                            msg = f"🐋 {symbol}大单{side}\n价格:{trade_price}\n金额:{int(value)}U"
                            await bot.send_message(chat_id=CHAT_ID, text=msg)

                    except:
                        continue

            await asyncio.sleep(20)

        except Exception as e:
            print("错误:", e)
            await asyncio.sleep(10)

async def main():
    global CHAT_ID

    updates = await bot.get_updates()
    if updates:
        CHAT_ID = updates[-1].message.chat.id

    await monitor()

asyncio.run(main())
