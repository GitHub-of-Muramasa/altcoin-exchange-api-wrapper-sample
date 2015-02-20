# -*- encoding:UTF-8 -*-
from abc import ABCMeta, abstractmethod
import hashlib, hmac, json, logging, time

import requests

import calculation
from reflection import class_for_name

logger = logging.getLogger(__name__)

'''
Created on 2015/02/11

@author: user

APIラッパー
'''
def get_api_wrapper(class_name):
    '''
    stringのクラス名からclassを得る
    '''
    return class_for_name(__name__, class_name)

class BaseApiWrapper():
    '''
    APIラッパーの基底クラス
    '''
    __metaclass__ = ABCMeta

    # APIの前回呼び出し時刻
    last_api_use = None

    def __init__(self, market_instance):
        self.exchange_name = market_instance.exchange_name
        self.api_available_span = market_instance.api_available_span
        self.base_currency = market_instance.base_currency
        self.counter_currency = market_instance.counter_currency
        self.fee = market_instance.fee
        self.bid_fee_is_gain = market_instance.bid_fee_is_gain
        self.ask_fee_is_gain = market_instance.ask_fee_is_gain
        self.min_price_unit = market_instance.min_price_unit
        self.min_trade_amount = market_instance.min_trade_amount
        self.min_trade_unit = market_instance.min_trade_unit

        self.last_api_use = time.time() - self.api_available_span
        logger.debug(self.last_api_use)

    def __wait_for_use_api(self):
        '''
        APIが使用可能になるまで待つ
        '''
        # 前回のAPI呼び出しから経過した時間
        time_from_last_use = time.time() - self.last_api_use
        logger.debug('time_from_last_use=%s', time_from_last_use)

        if time_from_last_use < self.api_available_span:
            time.sleep(self.api_available_span - time_from_last_use)

    def send_get(self, url, **kwargs):
        '''
        GETリクエストを送信する
        '''
        self.__wait_for_use_api()

        r = requests.get(url, **kwargs)
        self.last_api_use = time.time()

        logger.debug('GET Request sended.')
        return r.text

    def send_post(self, url, data=None, json=None, **kwargs):
        '''
        POSTリクエストを送信する
        '''
        self.__wait_for_use_api()

        r = requests.post(url, data, json, **kwargs)
        self.last_api_use = time.time()

        logger.debug('POST Request sended.')
        return r.text

    @abstractmethod
    def depth(self):
        '''
        depth情報を得る
        '''
        pass

    def get_order_price(self, order):
        '''
        depthの一注文の価格を得る
        '''
        return calculation.kiri_sute(order[0], self.min_price_unit)

    def get_order_amount(self, order):
        '''
        depthの一注文の数量を得る
        '''
        return calculation.kiri_sute(order[1], self.min_trade_unit)

    def get_buy_orders(self):
        '''
        depthから買い注文一覧を得る
        '''
        # 価格の降順
        return sorted(json.loads(self.depth())['bids']
                , key=self.get_order_price, reverse=True
        )

    def get_sell_orders(self):
        '''
        depthから売り注文一覧を得る
        '''
        # 価格の昇順
        return sorted(json.loads(self.depth())['asks']
                , key=self.get_order_price
        )

    def get_buy_order_gain(self, amount):
        '''
        買い注文で取得する数量を得る
        '''
        return amount * (100 - self.fee) / 100 if self.bid_fee_is_gain else amount

    def get_buy_order_pay(self, amount):
        '''
        買い注文で支払う数量を得る
        '''
        return amount if self.bid_fee_is_gain else amount * (100 + self.fee) / 100

    def get_sell_order_gain(self, amount):
        '''
        売り注文で取得する数量を得る
        '''
        return amount * (100 - self.fee) / 100 if self.ask_fee_is_gain else amount

    def get_sell_order_pay(self, amount):
        '''
        売り注文で支払う数量を得る
        '''
        return amount if self.ask_fee_is_gain else amount * (100 + self.fee) / 100

class AllCoinApiWrapper(BaseApiWrapper):
    '''
    AllCoin.com APIラッパー
    https://www.allcoin.com/pub/api
    '''
    def get_depth_url(self):
        '''
        depth取得URL
        '''
        return 'https://www.allcoin.com/api2/orderbook/' \
                + self.base_currency.upper() + '_' + self.counter_currency.upper()

    def depth(self):
        '''
        Market Orders(There are two types of the depth API)
        GET: https://www.allcoin.com/api2/orderbook/[coin1]_[coin2]
        https://www.allcoin.com/api2/orderbook/DOGE_BTC
        {
            "code": 1,
            "data": {
                "sell": [
                    {
                        "price": "0.00000066",
                        "amount": 1524976.1445662
                    },
                    {
                        "price": "0.00000067",
                        "amount": 2961630.0806241
                    },
                    ...
               ],
                "buy": [
                    {
                        "price": "0.00000065",
                        "amount": 760991.062875
                    },
                    {
                        "price": "0.00000064",
                        "amount": 2289778.703125
                    },
                    ...
              ]
            }
        }
        '''
        return self.send_get(self.get_depth_url())

    def get_order_price(self, order):
        '''
        depthの一注文の価格を得る
        '''
        return calculation.kiri_sute(float(order['price']), self.min_price_unit)

    def get_order_amount(self, order):
        '''
        depthの一注文の数量を得る
        '''
        return calculation.kiri_sute(order['amount'], self.min_trade_unit)

    def get_buy_orders(self):
        '''
        depthから買い注文一覧を得る
        '''
        # 価格の降順
        return sorted(json.loads(self.depth())['data']['buy']
                , key=self.get_order_price, reverse=True
        )

    def get_sell_orders(self):
        '''
        depthから売り注文一覧を得る
        '''
        # 価格の昇順
        return sorted(json.loads(self.depth())['data']['sell']
                , key=self.get_order_price
        )

    def get_auth_api_url(self):
        '''
        Wallet API ( Authentication required)
        のURL取得
        '''
        return 'https://www.allcoin.com/api2/auth_api/'

    def __add_sign(self, post_params):
        '''
        All requests to the Wallet and Trading methods require authentication
        via a public and private API key pair.
        An authenticated API request must contain the following three items.
        NAME          DESCRIPTION
        access_key    Your public key
        created       UTC timestamp
        sign          MD5 all your POST DATA( your parameters must be sorted from a~z)
        '''
        # 暗号化用の文字列を作成
        for_sign = '&'.join(
                [param_key + '=' + str(post_params[param_key])
                        for param_key in sorted(post_params)
                ]
        )
        logger.debug('for_sign=%s', for_sign)

        # signを作成
        sign = hashlib.md5(for_sign).hexdigest()
        logger.debug('sign=%s', sign)

        return post_params.update({'sign': sign})

    def __execute_auth_api(self, public_key, secret_key, method, post_params={}):
        '''
        Authenticationが必要なAPIを実行する
        '''
        # 必須のPOSTパラメータを追加
        # 秘密鍵もPOSTパラメータに混ぜるよく分からない方法
        post_params.update({
                'access_key': public_key, 'created': time.time(),
                'method': method, 'secret_key': secret_key,
        })

        # signの設定
        self.__add_sign(post_params)

        # POSTリクエストを実行
        return self.send_post(self.get_auth_api_url(), data=post_params)

    def account_info(self, public_key, secret_key):
        '''
        Account Informations
        POST: https://www.allcoin.com/api2/auth_api/
        Parameters
        NAME          TYPE      REQUIRED    DESCRIPTION
        access_key    String       Yes    Access key
        created       Timestamp    Yes    UTC Timestamp
        method        getinfo      Yes    Function name
        sign          String       Yes    Sign the params with your private_key
        '''
        return self.__execute_auth_api(public_key, secret_key, 'getinfo')

    def sell_coin(self, public_key, secret_key, price, num):
        '''
        Sell Coin
        POST: https://www.allcoin.com/api2/auth_api/
        Parameters
        NAME          TYPE    REQUIRED    DESCRIPTION
        access_key    String       Yes    Access key
        created       Timestamp    Yes    UTC Timestamp
        exchange      String       Yes    BTC LTC DOGE
        method        sell_coin    Yes    Function name
        num           Decimal      Yes    Order num
        price         Decimal      Yes    Order price
        sign          String       Yes    Sign the params with your private_key
        type          String       Yes    coin type: DOGE BC DRK...
        '''
        # 価格、数量の整形
        price = calculation.kiri_sute(price, self.min_price_unit)
        num = calculation.kiri_sute(num, self.min_trade_unit)
        logger.debug('price=%s, amount=%s', price, num)

        post_params = {
                'exchange': self.counter_currency.upper(),
                'num': num, 'price': price,
                'type': self.base_currency.upper()
        }
        return self.__execute_auth_api(public_key, secret_key, 'sell_coin', post_params)

    def buy_coin(self, public_key, secret_key, price, num):
        '''
        Buy Coin
        POST: https://www.allcoin.com/api2/auth_api/
        Parameters
        NAME          TYPE    REQUIRED    DESCRIPTION
        access_key    String       Yes    Access key
        created       Timestamp    Yes    UTC Timestamp
        exchange      String       Yes    BTC LTC DOGE
        method        buy_coin     Yes    Function name
        num           Decimal      Yes    Order num
        price         Decimal      Yes    Order price
        sign          String       Yes    Sign the params with your private_key
        type          String       Yes    coin type: DOGE BC DRK...
        '''
        # 価格、数量の整形
        price = calculation.kiri_sute(price, self.min_price_unit)
        num = calculation.kiri_sute(num, self.min_trade_unit)
        logger.debug('price=%s, amount=%s', price, num)

        post_params = {
                'exchange': self.counter_currency.upper(),
                'num': num, 'price': price,
                'type': self.base_currency.upper()
        }
        return self.__execute_auth_api(public_key, secret_key, 'buy_coin', post_params)

    def cancel_order(self, public_key, secret_key, order_id):
        '''
        Cancel Order
        POST: https://www.allcoin.com/api2/auth_api/
        Parameters
        NAME          TYPE         REQUIRED    DESCRIPTION
        access_key    String         Yes    Access key
        created       Timestamp      Yes    UTC Timestamp
        method        cancel_order   Yes    Function name
        order_id      Integer        Yes    Order Id
        sign          String         Yes    Sign the params with your private_key
        '''
        post_params = {'order_id': order_id}
        return self.__execute_auth_api(public_key, secret_key, 'cancel_order', post_params)

class BtcBoxApiWrapper(BaseApiWrapper):
    '''
    BtcBox APIラッパー
    https://www.btcbox.co.jp/help/api.html
    '''
    def get_api_url(self, func_name):
        '''
        各種APIアクセス用URLを取得
        '''
        return 'https://www.btcbox.co.jp/api/v1/' + func_name + '/'

    def depth(self):
        '''
        Depth
            Market Depth, Return data is large, Do not frequently use。
            Path：https://www.btcbox.co.jp/api/v1/depth/
            Request method：GET
            Parameters
                none
                Return JSON dictionary
                asks - represents sell orders, format is: [price, quantity],
                        the orders are ranked according to price from high to low.
                bids - represents buy orders, format is: [price, quantity],
                        the orders are ranked according to price from high to low.
            Return：
                depth取得正規表現
                {
                    "asks":\[\[(?P<ask_price>\d+),(?P<ask_amount>\d+(\.\d)?),?\]\],
                    "bids":\[\[(?P<bid_price>\d+),(?P<bid_amount>\d+(\.\d)?),?\]\]
                }
        '''
        return self.send_get(
                self.get_api_url('depth'), params={'coin': self.base_currency.lower()}
        )

    def __make_signature(self, post_params, public_key, secret_key):
        '''
        signature -- Parameters like "amount", "price", "type",
        "nonce", "key" will be combined by '&' to create a new string,
        encrypt the new string by Sha256 algorithm, key is md5(private key)
        '''
        # 必須のPOSTパラメータを追加
        post_params.update({'nonce': str(int(time.time())), 'key': public_key})

        # 秘密鍵で署名を行う文字列を作成
        for_signature = '&'.join(
                [param_key + '=' + str(post_params[param_key]) for param_key in post_params]
        )
        logger.debug('for_signature=%s', for_signature)

        # 秘密鍵で署名を行う
        signature = hmac.new(hashlib.md5(str(secret_key)).hexdigest()
                , for_signature, hashlib.sha256
        ).hexdigest()
        logger.debug('signature=%s', signature)

        # POSTパラメーターにsignatureを追加
        post_params.update({'signature': signature})

    def __execute_auth_api(self, public_key, secret_key, func_name, post_params={}):
        '''
        Authenticationが必要なAPIを実行する
        '''
        # signatureの設定
        self.__make_signature(post_params, public_key, secret_key)

        # POSTリクエストを実行
        return self.send_post(self.get_api_url(func_name), data=post_params)

    def account_balance(self, public_key, secret_key):
        '''
        Account Balance
            Account information
            Path：https://www.btcbox.co.jp/api/v1/balance/
            Request method：POST
            Parameters
                key - API key
                signature - signature
                nonce - nonce
            Return JSON dictionary
                jpy_balance - Total JPY
                btc_balance - Total BTC
                jpy_lock - Lock JPY
                btc_lock - Lock BTC
                nameauth - Real-name authentication status, 0 -> no, 1 -> wait, 2 -> success
                moflag - Cellphone status, 0 -> no ,1 -> yes
            Return：
                {
                    "uid":8,"nameauth":0,"moflag":0,
                    "btc_balance":4234234,"btc_lock":0,
                    "ltc_balance":32429.6,"ltc_lock":2.4,
                    "doge_balance":0,"doge_lock":0,
                    "jpy_balance":2344581.519,"jpy_lock":868862.481
                }
        '''
        return self.__execute_auth_api(public_key, secret_key, 'balance')

    def wallet(self, public_key, secret_key):
        '''
        Wallet
            Path：https://www.btcbox.co.jp/api/v1/wallet/
            Request method：POST
            Parameters
                key - API key
                signature - signature
                nonce - nonce
            Return JSON dicitionary
                result - true(success), false(fail)
                address - Bitcoin address
            Return:
                {"result":true, "address":"1xxxxxxxxxxxxxxxxxxxxxxxx"}
        '''
        post_params = {'coin': self.base_currency.lower()}
        return self.__execute_auth_api(public_key, secret_key, 'wallet', post_params)

    def trade_list(self, public_key, secret_key, since, order_type):
        '''
        Trade_list
        return trade list by timestamp or trade type
            Path：https://www.btcbox.co.jp/api/v1/trade_list/
            Request method：POST
            Parameters
                key - API key
                signature - signature
                nonce - nonce
                since - unix timestamp(utc timezone) default == 0
                type - [open or all]
            Return JSON dictionary
                id - ID
                datetime - date and time
                type - "buy" or "sell"
                price - price
                amount_original - total number
                amount_outstanding - The number of remaining
            Return：
                [
                    {
                        "id":"11","datetime":"2014-10-21 10:47:20","type":"sell",
                        "price":42000,"amount_original":1.2,"amount_outstanding":1.2
                    }
                    ,{"id":"10","datetime":"2014-10-20 13:29:39","type":"sell",
                        "price":42000,"amount_original":1.2,"amount_outstanding":1.2
                    }
                    ,{
                        "id":"9","datetime":"2014-10-20 13:29:29","type":"sell",
                        "price":42000,"amount_original":1.2,"amount_outstanding":1.2
                    }
                    ,{
                        "id":"3","datetime":"2014-10-20 13:25:57","type":"buy",
                        "price":43200,"amount_original":0.4813,"amount_outstanding":0.4813
                    }
                ]
        '''

    def trade_view(self, public_key, secret_key, order_id):
        '''
        Trade_view
            Path：https://www.btcbox.co.jp/api/v1/trade_view/
            Request method：POST
            Parameters
                key - API key
                signature - signature
                nonce - nonce
                id - ID
                Return JSON dictionary
                id - ID
                datetime - format：YYYY-mm-dd HH:ii:ss）
                type - "buy" or "sell"
                price - price
                amount_original - total number
                amount_outstanding - The number of remaining
                status - Order status：no, part, cancelled, all
                trades - JSON dictionary list:
                    trade_id - ID
                    amount - Number of transactions
                    price - price of transactions
                    datetime - format：YYYY-mm-dd HH:ii:ss）
                    fee
            Return：
                {
                    "id":11,"datetime":"2014-10-21 10:47:20",
                    "type":"sell","price":42000,
                    "amount_original":1.2,"amount_outstanding":1.2,
                    "status":"closed"
                    ,"trades":[]
                }
        '''

    def trade_cancel(self, public_key, secret_key, order_id):
        '''
        Trade_cancel
            Path：https://www.btcbox.co.jp/api/v1/trade_cancel/
            Request method：POST
            Parameters
                key - API key
                signature - signature
                nonce - nonce
                id - ID
            Return JSON dictionary
                result - true(success), false(fail)
                id - ID
            Return：
                {"result":true, "id":"11"}
        '''
        post_params = {'id': order_id}
        return self.__execute_auth_api(public_key, secret_key, 'trade_cancel', post_params)

    def trade_add(self, public_key, secret_key, is_buy_order, price, amount):
        '''
        Trade_add
            Path：https://www.btcbox.co.jp/api/v1/trade_add/
            Request method：POST
            Parameters
                key - API key
                signature - signature
                nonce - nonce
                amount - Total number
                price
                type - buy or sell
            Return JSON dictionary
                id - ID
                result - true(success), false(fail)
            Return：
                {"result":true, "id":"11"}
        '''
        # 価格、数量の整形
        price = calculation.kiri_sute(price, self.min_price_unit)
        amount = calculation.kiri_sute(amount, self.min_trade_unit)
        logger.debug('price=%s, amount=%s', price, amount)

        # POSTパラメーターの作成
        post_params = {
                'type': 'buy' if is_buy_order else 'sell',
                'amount': amount, 'price': price,
                # APIドキュメントに書かれていないkey、ふざけんな
                'coin': self.base_currency.lower(),
        }
        return self.__execute_auth_api(public_key, secret_key, 'trade_add', post_params)

class EtwingsApiWrapper(BaseApiWrapper):
    '''
    etwings APIラッパー
    https://exchange.etwings.com/doc_api
    '''
    def get_depth_url(self):
        '''
        depth取得URL
        '''
        base_url = 'https://exchange.etwings.com/api/1/depth/'
        return base_url+ self.base_currency.lower() + '_jpy'

    def depth(self):
        '''
        depth情報を得る
        '''
        return self.send_get(self.get_depth_url())

    def get_auth_api_url(self):
        '''
        Trade APIのURL
        '''
        return 'https://exchange.etwings.com/tapi'

    def __create_http_headers(self, post_params, secret_key, key):
        '''
        Trade APIに必要なHTTP Headerを作成する
        '''
        # 秘密鍵で署名を行う文字列を作成
        for_sign = '&'.join(
                [param_key + '=' + str(post_params[param_key]) for param_key in post_params]
        )
        logger.debug('for_sign=%s', for_sign)

        # 秘密鍵で署名を行う
        sign = hmac.new(str(secret_key), for_sign, hashlib.sha512).hexdigest()
        logger.debug('sign=%s', sign)

        return {'key': key, 'sign': sign,}

    def __execute_auth_api(self, public_key, secret_key, method, post_params):
        '''
        Trade APIにPOSTリクエストを送信し、結果を返す
        '''
        # 必須のPOSTパラメータを追加
        post_params.update({'method': method, 'nonce': str(int(time.time()))})

        # HTTP Headerを作成
        headers = self.__create_http_headers(post_params, secret_key, public_key)

        # POSTリクエストを実行
        return self.send_post(
                self.get_auth_api_url(), data=post_params, headers=headers
        )

    def get_info(self, public_key, secret_key):
        '''
        Returns the information about the user's current balance,
        API key permissions,the number of past trades,
        the number of active orders and the server time.
        '''
        post_params = {}
        return self.__execute_auth_api(public_key, secret_key, 'get_info', post_params)

    def trade(self, public_key, secret_key, is_buy_order, price, amount):
        '''
        Issue an order.
        '''
        # 価格、数量の整形
        price = calculation.kiri_sute(price, self.min_price_unit)
        amount = calculation.kiri_sute(amount, self.min_trade_unit)
        logger.debug('price=%s, amount=%s', price, amount)

        # POSTパラメーターの作成
        post_params = {
                'currency_pair': self.base_currency.lower() + '_jpy',
                'action': 'bid' if is_buy_order else 'ask',
                'price': price, 'amount': amount
        }

        return self.__execute_auth_api(public_key, secret_key, 'trade', post_params)

    def cancel_order(self, public_key, secret_key, order_id):
        '''
        Cancellation of the order.
        '''
        post_params = {'order_id': order_id}
        return self.__execute_auth_api(public_key, secret_key, 'cancel_order', post_params)
