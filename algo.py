"""
Paper Trading - https://testnet.binance.vision/
Guide - https://algotrading101.com/learn/binance-python-api-guide/

"""
import logging as log
import signal
import sys
import time
from threading import Thread, Event

import schedule
import telebot
from binance.client import Client
from binance.websockets import BinanceSocketManager
from twisted.internet import reactor

"""
Configurations
"""
# TODO: externalize to env variables
tg_notification_group_id = -427619077
binance_api_endpoint = 'https://api.binance.com/api'
api_key = 'wr0rFGK0Gbl2pHp4qB0xANsp6p7AeWgqlKaBAVFIok8adIy4hqB7IKIHeWoanZlx'
api_secret = '6TKiIPzMmcEjePab9cNfnZkrpOZdjms4os5siS6fA2t0shwKDsmeyyE0JE8CXg0l'
telebot_token = '1785575987:AAFadtnwM8WCIAJ8Xxz7MgJs3ZhU0QOmXfc'

"""
Initialization
"""
tg_bot = telebot.TeleBot(telebot_token)
binance_client = Client(api_key, api_secret)
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
    'is_telegram_bot_on': True,
    'is_binance_trading_enabled': False
}

"""
Strategy variables
"""
trading_signal = {
    'sma': 0,
    'rsi': 0
}
ma_5 = -1.0
ma_10 = -1.0
btc_usdt_price = -1.0

"""
Telegram bot commands
"""


def tg_bot_polling():
    log.info('Telegram bot polling started.')
    tg_bot.polling()


def notify_buy_signal(reason):
    notify('$$$$ BUY signal at {} by {} $$$$'.format(btc_usdt_price, reason))
    log.info('$$$$ BUY signal at {} by {} $$$$'.format(btc_usdt_price, reason))


def notify_sell_signal(reason):
    notify('$$$$ SELL signal at {} by {} $$$$'.format(btc_usdt_price, reason))
    log.info('$$$$ SELL signal at {} by {} $$$$'.format(btc_usdt_price, reason))


def notify(msg):
    try:
        api_reply = tg_bot.send_message(tg_notification_group_id, msg)
        if api_reply is not None:
            log.info('Message sent.')
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


@tg_bot.message_handler(commands=['snapshot'])
def sys_snapshot(message):
    log.info('Received command: ' + message.text)
    notify(generate_sys_snapshot_str())


"""
Functions
"""


def generate_sys_snapshot_str():
    def gen_dict_str(dictionary: dict):
        s = '\n'
        for k in dictionary.keys():
            s += '- {}: {}\n'.format(k, dictionary[k])
        return s

    str = '**** System Snapshot ****\n'
    str += 'app_args: {}\n'.format(gen_dict_str(app_args))
    str += 'ma_5: {}\n'.format(ma_5)
    str += 'ma_10: {}\n'.format(ma_10)
    str += 'btc_usdt_price: {}\n'.format(btc_usdt_price)
    str += 'trading_signal: {}\n'.format(gen_dict_str(trading_signal))

    return str


def calculate_sma():
    global ma_5
    global ma_10
    log.info('Started to calculate SMA.')
    kline_5 = binance_client.get_historical_klines('BTCUSDT', Client.KLINE_INTERVAL_1DAY, '5 days ago UTC')
    kline_10 = binance_client.get_historical_klines('BTCUSDT', Client.KLINE_INTERVAL_1DAY, '10 days ago UTC')
    ma_5 = get_avg_close(kline_5)
    log.info('5 days MA saved: {}.'.format(ma_5))
    ma_10 = get_avg_close(kline_10)
    log.info('10 days MA saved: {}.'.format(ma_10))
    log.info('Finish SMA calculation.')


def fetch_btc_usdt_price():
    global btc_usdt_price
    # last 1 minute
    klines = binance_client.get_klines(symbol='BTCUSDT', interval=Client.KLINE_INTERVAL_1MINUTE, limit=1)
    close = klines[0][4]
    btc_usdt_price = float(close)
    log.debug('BTC/USDT price fetched: {}.'.format(close))


def trading_strategy():
    global trading_signal
    if btc_usdt_price > ma_5 > ma_10 and trading_signal['sma'] < 1:
        trading_signal['sma'] = 1
        notify_buy_signal('Golden Cross')

    if btc_usdt_price < ma_5 < ma_10 and trading_signal['sma'] > -1:
        trading_signal['sma'] = -1
        notify_sell_signal('Death Cross')


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
        # TODO: log more info for better traceability
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
        notify('Exit Application.')
        sys.exit(0)


def get_avg_close(binance_klines):
    closes = [float(x[4]) for x in binance_klines]
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
        elif '--binance-trading-enable' in arg:
            val = arg[1].upper()
            if val in TRUE_ALIAS:
                app_args['is_binance_trading_enabled'] = True

    log.info('App Args: {}'.format(app_args))


if __name__ == "__main__":
    # Initialize application arguments
    init_params(sys.argv[1:])

    """ Thread 1: polling telegram commands """
    if app_args['is_telegram_bot_on']:
        tg_thread = Thread(target=tg_bot_polling)
        tg_thread.daemon = True
        tg_thread.start()
        log.info('Telegram process started.')

    """ Thread 2: running scheduled tasks """
    if app_args['is_schedule_tasks_on']:
        # run them once at first to initialize data
        log.info('Initializing mandatory data...')
        fetch_btc_usdt_price()
        calculate_sma()
        trading_strategy()
        log.info('Finished data initialization.')
        schedule.every().minute.do(calculate_sma)
        schedule.every().minute.do(fetch_btc_usdt_price)
        schedule.every().minute.do(trading_strategy)
        sch_thread = Thread(target=run_scheduled_tasks)
        sch_thread.daemon = True
        sch_thread.start()
        log.info('Schedule task process started.')

    if app_args['is_data_stream_on']:
        # TODO: start this in another thread
        bsm = BinanceSocketManager(binance_client)
        conn_key = bsm.start_symbol_ticker_socket('BTCUSDT', btcusdt_tick_handler)
        log.info('Data streaming started.')
        bsm.start()

    # Handle system signals
    signal.signal(signal.SIGINT, gracfully_close_handler)
    signal.signal(signal.SIGQUIT, gracfully_close_handler)
    signal.signal(signal.SIGTERM, gracfully_close_handler)
    log.info('Application started.')
    notify('Application started.')
    forever = Event()
    forever.wait()
