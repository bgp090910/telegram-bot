import os
import requests
import asyncio
from telegram import Bot

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = Bot(token=TELEGRAM_TOKEN)

CHAT_ID = None

symbols = ["BTCUSDT", "ETHUSDT"]

last_prices = {}

# 获取价格
def get_price(symbol):
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
    return float(requests.get(url).json()['price'])

# 获取最近成交（用于检测大单）
def get_trades(symbol):
    url = f"https://api.binance.com/api/v3/trades?symbol={symbol}&limit=50"
    return requests.get(url).json()

async def monitor():
    global CHAT_ID

    while True:
        for symbol in symbols:
            price = get_price(symbol)
            trades = get_trades(symbol)

            # ===== 价格监控 =====
            if symbol in last_prices:
                change = (price - last_prices[symbol]) / last_prices[symbol]

                if change > 0.01:
                    msg = f"🚨 {symbol}上涨\n价格: {price}\n👉 可能突破"
                    await bot.send_message(chat_id=CHAT_ID, text=msg)

                elif change < -0.01:
                    msg = f"⚠️ {symbol}下跌\n价格: {price}\n👉 注意风险"
                    await bot.send_message(chat_id=CHAT_ID, text=msg)

            last_prices[symbol] = price

            # ===== 主力大单检测 =====
            for trade in trades:
                qty = float(trade['qty'])
                trade_price = float(trade['price'])
                value = qty * trade_price

                if value > 100000:  # 10万U大单
                    side = "买入" if not trade['isBuyerMaker'] else "卖出"

                    msg = (
                        f"🐋 {symbol}大单{side}\n"
                        f"价格: {trade_price}\n"
                        f"金额: {int(value)} USDT"
                    )

                    await bot.send_message(chat_id=CHAT_ID, text=msg)

        await asyncio.sleep(10)

async def main():
    global CHAT_ID

    updates = await bot.get_updates()
    if updates:
        CHAT_ID = updates[-1].message.chat.id

    await monitor()

asyncio.run(main())
