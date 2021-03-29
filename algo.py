"""
Paper Trading - https://testnet.binance.vision/
Guide - https://algotrading101.com/learn/binance-python-api-guide/

"""
import logging as log
import signal
import sys
import time
from datetime import datetime
from threading import Thread, Event

import schedule
import telebot
from binance.client import Client
from binance.websockets import BinanceSocketManager
from twisted.internet import reactor

"""
Configurations
"""
tg_notification_group_id = -427619077
binance_api_endpoint = 'https://testnet.binance.vision/api'
paper_api_key = 'zLIvCfgCOjjLFxIFVpTw9kdXDSTAdK9h3vZtwpSJ4YOY1kxpAjW1RagzBJ147qYV'
paper_api_secret = 'n4FC7mYB4095D8c81Xn3XHmlDhImztFYXYqiexPziuX1hCsPLoeHAeCsq68EWhy5'
telebot_token = '1785575987:AAFadtnwM8WCIAJ8Xxz7MgJs3ZhU0QOmXfc'

"""
Initialization
"""
tg_bot = telebot.TeleBot(telebot_token)
binance_client = Client(paper_api_key, paper_api_secret)
binance_client.API_URL = binance_api_endpoint
btc_price = {'error': False}
conn_key = None
log.basicConfig(format='%(asctime)s [%(levelname)s]: %(message)s', level=log.INFO)

"""
Application params
"""
app_args = {
    'is_data_stream_on': True,
    'is_print_stream_value': True,
    'is_schedule_tasks_on': True,
    'is_telegram_bot_on': True
}
"""
Telegram bot commands
"""


def tg_bot_polling():
    log.info('Telegram bot polling started.')
    tg_bot.polling()


def notify(msg):
    try:
        api_reply = tg_bot.send_message(tg_notification_group_id, msg)
        if api_reply is not None:
            log.info('Reply sent.')
    except Exception as e:
        log.info('Telegram Error: {}'.format(e))


@tg_bot.message_handler(commands=['balance'])
def check_balance(message):
    log.info('Received command: ' + message.text)
    notify(generate_balance_string())


@tg_bot.message_handler(commands=['balance_btcusdt'])
def check_balance_btcusdt(message):
    log.info('Received command: ' + message.text)
    notify(generate_balance_string(['BTC', 'USDT']))


@tg_bot.message_handler(commands=['trade'])
def trade(message):
    log.info('Received command: ' + message.text)
    args = message.text.split(' ')
    if len(args) != 4:
        notify('Syntax Error. /trade [symbol] [side] [qty]')
        return
    try:
        symbol = args[1].upper()
        side = args[2].upper()
        qty = float(args[3])

        order = trade(symbol, side, qty)
        str = '{} order status: {},\nOriginal qty: {},\nFilled qty: {}'.format(
            order['side'],
            order['status'],
            order['origQty'],
            order['executedQty']
        )
        notify(str)
    except Exception as e:
        notify('Error: {}'.format(e))


"""
Functions
"""


def test_10s():
    log.info('Scheduled job executed')


def run_scheduled_tasks():
    while True:
        schedule.run_pending()
        time.sleep(60 * 60)  # 1 hour
        # time.sleep(2)  # 2 seconds


def trade(symbol, side, qty):
    order = binance_client.create_order(
        symbol=symbol,
        side=side,
        type='MARKET',
        quantity=qty)
    return order


def generate_balance_string(assets=None):
    str = ''
    str += '*********** Balance **********\n'
    for currency in binance_client.get_account()['balances']:
        if float(currency['free']) <= 0 and float(currency['locked']) <= 0:
            continue
        if assets is not None and currency['asset'] not in assets:
            continue
        str += '{}: {}\n'.format(currency['asset'], currency['free'])
    str += '******************************'
    return str


def print_balance_btc_usdt():
    print_balance(['BTC', 'USDT'])


def print_balance(assets=None):
    log.info(generate_balance_string(assets))


def sell_all_assets_to_usdt():
    """
    Try to sell all assets to USDT
    :return:
    """
    for currency in binance_client.get_account()['balances']:
        if currency['asset'] == 'USDT':
            continue
        if float(currency['free']) <= 0 and float(currency['locked']) <= 0:
            continue
        sell_asset_to_usdt(currency['asset'], currency['free'])
        print_balance()


def sell_asset_to_usdt(symbol, quantity):
    """
    Sell an asset to USDT if the currency pair exists
    :param symbol:
    :param quantity:
    :return:
    """
    symbol = symbol + 'USDT'
    try:
        binance_client.create_order(
            symbol=symbol,
            side='SELL',
            type='MARKET',
            quantity=quantity)
        log.info('Order Filled.')
    except Exception as e:
        log.info('Error: Currency: {}, {}'.format(symbol, e))


def btcusdt_tick_handler(msg):
    """ define how to process incoming WebSocket messages """
    global app_args
    if msg['e'] != 'error':
        if app_args['is_print_stream_value']:
            log.info(msg['c'])
        btc_price['last'] = msg['c']
        btc_price['bid'] = msg['b']
        btc_price['last'] = msg['a']
    else:
        btc_price['error'] = True


def gracfully_close_handler(signal, frame):
    try:
        bsm.stop_socket(conn_key)  # stop websocket
        reactor.stop()  # properly terminate WebSocket
        log.info('Gracefully terminated.')
    except NameError:
        log.info('Gracefully terminated, Data stream socket is not started.')
    finally:
        log.info('Exit Application.')
        sys.exit(0)


def get_avg_close(binance_klines):
    closes = [float(x[4]) for x in binance_klines]
    for x in binance_klines:
        ts = datetime.fromtimestamp(x[0] / 1000)
        log.info(ts)
    log.info(closes)
    return sum(closes) / len(closes)


def init_params(args):
    global app_args

    TRUE_ALIAS = ['TRUE', 'T', 'ON', 'Y', 'YES', 'ENABLED', 'ENABLE']
    for arg in args:
        arg = arg.split('=')
        if '--data-stream' in arg:
            val = arg[1].upper()
            if val not in TRUE_ALIAS:
                app_args['is_data_stream_on'] = False
        elif '--stream-print' in arg:
            val = arg[1].upper()
            if val not in TRUE_ALIAS:
                app_args['is_print_stream_value'] = False
        elif '--schedule-task' in arg:
            val = arg[1].upper()
            if val not in TRUE_ALIAS:
                app_args['is_schedule_tasks_on'] = False
        elif '--telegram-bot' in arg:
            val = arg[1].upper()
            if val not in TRUE_ALIAS:
                app_args['is_telegram_bot_on'] = False

    log.info('App Args: {}'.format(app_args))


if __name__ == "__main__":
    init_params(sys.argv[1:])
    kline = binance_client.get_historical_klines('BTCUSDT', Client.KLINE_INTERVAL_1DAY, '10 day ago UTC')
    # 10 day ago UTC
    # '17 Mar, 2021', '27 Mar, 2021'
    # log.info(kline)

    """ Thread 1: polling telegram commands """
    if app_args['is_telegram_bot_on']:
        tg_thread = Thread(target=tg_bot_polling)
        tg_thread.daemon = True
        tg_thread.start()
        log.info('Telegram process started.')

    """ Thread 2: running scheduled tasks """
    if app_args['is_schedule_tasks_on']:
        # run them once at first to initialize data
        test_10s()
        # schedule.every().day.do(test_10s)
        schedule.every().second.do(test_10s)
        sch_thread = Thread(target=run_scheduled_tasks)
        sch_thread.start()
        log.info('Schedule task process started.')

    if app_args['is_data_stream_on']:
        bsm = BinanceSocketManager(binance_client)
        conn_key = bsm.start_symbol_ticker_socket('BTCUSDT', btcusdt_tick_handler)
        log.info('Data streaming started.')
        bsm.start()

    # Handle system signals
    signal.signal(signal.SIGINT, gracfully_close_handler)
    signal.signal(signal.SIGQUIT, gracfully_close_handler)
    signal.signal(signal.SIGTERM, gracfully_close_handler)
    log.info('Application started.')
    forever = Event()
    forever.wait()
