import asyncio
import os

import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN environment variable is required")

SYMBOLS = ["BTCUSDT", "ETHUSDT"]
PRICE_CHANGE_THRESHOLD = 0.01
TRADE_ALERT_USD = 100000
MONITOR_INTERVAL_SECONDS = 20

chat_ids = set()
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
    if data and "price" in data:
        return float(data["price"])
    return None


def get_trades(symbol):
    return safe_request(f"https://api.binance.com/api/v3/trades?symbol={symbol}&limit=20") or []


def format_price_snapshot():
    lines = []
    for symbol in SYMBOLS:
        price = get_price(symbol)
        if price is None:
            lines.append(f"{symbol}: 获取失败")
        else:
            lines.append(f"{symbol}: {price}")
    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_ids.add(update.effective_chat.id)
    await update.message.reply_text(
        "机器人已启动，已把你加入监控名单。\n\n"
        "可用命令：\n"
        "/price 查看 BTC 和 ETH 最新价格\n"
        "/status 查看当前监控状态"
    )


async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_ids.add(update.effective_chat.id)
    await update.message.reply_text(format_price_snapshot())


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_ids.add(update.effective_chat.id)
    await update.message.reply_text(
        "监控运行中\n"
        f"币种: {', '.join(SYMBOLS)}\n"
        f"价格波动阈值: {PRICE_CHANGE_THRESHOLD * 100:.0f}%\n"
        f"大单阈值: {TRADE_ALERT_USD:.0f}U\n"
        f"已订阅聊天数: {len(chat_ids)}"
    )


async def send_to_subscribers(application: Application, text: str):
    for chat_id in list(chat_ids):
        try:
            await application.bot.send_message(chat_id=chat_id, text=text)
        except Exception as exc:
            print(f"发送到 {chat_id} 失败: {exc}")


async def monitor(application: Application):
    while True:
        try:
            for symbol in SYMBOLS:
                price = get_price(symbol)
                if price is None:
                    continue

                previous_price = last_prices.get(symbol)
                trades = get_trades(symbol)

                if previous_price:
                    change = (price - previous_price) / previous_price
                    if abs(change) > PRICE_CHANGE_THRESHOLD and chat_ids:
                        await send_to_subscribers(
                            application,
                            f"{symbol} 变动 {round(change * 100, 2)}%\n价格: {price}",
                        )

                last_prices[symbol] = price

                for trade in trades:
                    try:
                        qty = float(trade["qty"])
                        trade_price = float(trade["price"])
                        value = qty * trade_price

                        if value > TRADE_ALERT_USD and chat_ids:
                            side = "买入" if not trade["isBuyerMaker"] else "卖出"
                            await send_to_subscribers(
                                application,
                                f"🐋 {symbol}大单{side}\n价格:{trade_price}\n金额:{int(value)}U",
                            )
                    except Exception:
                        continue

            await asyncio.sleep(MONITOR_INTERVAL_SECONDS)
        except Exception as exc:
            print("监控错误:", exc)
            await asyncio.sleep(10)


async def post_init(application: Application):
    application.create_task(monitor(application))


def main():
    application = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("price", price))
    application.add_handler(CommandHandler("status", status))
    application.run_polling()


if __name__ == "__main__":
    main()
