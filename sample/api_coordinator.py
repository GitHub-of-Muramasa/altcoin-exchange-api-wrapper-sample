# -*- encoding:UTF-8 -*-
import logging

import calculation, constants

logger = logging.getLogger(__name__)

'''
Created on 2015/02/11

@author: user

- 処理速度を高めるため、if文の使用は控えたい
- 全ての取引所APIに対し、画一的なインタフェースでアクセス可能にすること
'''
def __get_order_with_base_amount(
        api_wrapper, price, amount, is_buy_order, order_price
        , fraction, order_list, left_amount, counter_sum
):
    '''
    注文数から約定を見込める注文を得る
    api_wrapper: 市場情報
    price: 判定対象となる注文の価格
    amount: 判定対象となる注文の数量

    is_buy_order: 買い注文かどうか(この関数では使用しない引数)
    order_price: 注文価格(この関数では使用しない引数)

    fraction: 前回注文までの最低注文数以下の注文数量合計
    order_list: 約定を見込める注文一覧
    left_amount: 残りの注文数量
    counter_sum: 相対通貨の取引数量(手数料未計算)
    '''
    # 最低注文数よりamountが少ない注文は、次の注文に含める
    if amount < api_wrapper.min_trade_amount:
        fraction = amount

    elif left_amount <= amount:
        # 注文数が注文に収まった場合
        fraction = 0
        order_list.append([price, left_amount])
        counter_sum += price * left_amount
        left_amount = 0

    else:
        # 注文数が注文に収まらなかった場合
        fraction = 0
        order_list.append([price, amount])
        counter_sum += price * amount
        left_amount -= amount

    return fraction, order_list, left_amount, counter_sum

def __get_order_with_order(
        api_wrapper, price, amount, is_buy_order, order_price
        , fraction, order_list, left_amount, counter_sum
):
    '''
    注文から約定を見込める注文を得る
    api_wrapper: 市場情報
    price: 判定対象となる注文の価格
    amount: 判定対象となる注文の数量
    is_buy_order: 買い注文かどうか
    order_price: 注文価格
    fraction: 前回注文までの最低注文数以下の注文数量合計
    order_list: 約定を見込める注文一覧
    left_amount: 残りの注文数量
    counter_sum: 相対通貨の取引数量(手数料未計算)
    '''
    if (is_buy_order and order_price >= price) or (not is_buy_order and order_price <= price):
        fraction, order_list, left_amount, counter_sum = __get_order_with_base_amount(
                api_wrapper, price, amount, is_buy_order, order_price
                , fraction, order_list, left_amount, counter_sum
        )

    return fraction, order_list, left_amount, counter_sum

def __get_order_plan(api_wrapper, is_buy_order, order_price, order_amount, get_order):
    '''
    注文情報から、約定を見込める(買い|売り)注文の一覧、各通貨の増減数量 を得る
    api_wrapper: 市場情報
    is_buy_order: 買い注文かどうか
    order_price: 注文価格
    order_amount: 注文数
    get_order: 注文を取得する関数
    '''
    # APIよりdepthを取得し、
    # 発注する注文一覧、注文可能数量、相対通貨数量(手数料未計算)を得る
    fraction = 0
    order_list = []
    left_amount = order_amount
    counter_sum = 0
    for order in api_wrapper.get_sell_orders() if is_buy_order else api_wrapper.get_buy_orders():
        if left_amount < api_wrapper.min_trade_amount:
            # 残りの注文数量が最低注文数量に満たない場合
            break

        logger.debug('order=%s', order)
        price = api_wrapper.get_order_price(order)
        amount = fraction + api_wrapper.get_order_amount(order)

        pre_fraction = fraction
        pre_counter_sum = counter_sum

        fraction, order_list, left_amount, counter_sum = get_order(
                api_wrapper, price, amount, is_buy_order, order_price
                , fraction, order_list, left_amount, counter_sum
        )
        logger.debug('fraction=%s, order_num=%s, left_amount=%s, counter_sum=%s'
                , fraction, len(order_list), left_amount, counter_sum
        )

        if counter_sum == pre_counter_sum and fraction == pre_fraction:
            # 注文が取得出来ない場合
            break

    # 注文一覧、注文可能数量、相対通貨数量(手数料未計算)
    orderable = order_amount - left_amount
    logger.debug('order_list=%s, orderable=%s, counter_sum=%s'
            , order_list, orderable, counter_sum
    )

    # 注文一覧、各通貨の増減数量 の順序で返す
    # TODO: 切り上げ、切り捨ての桁は何を基準に設定すればいい？
    return order_list \
            , {
                    api_wrapper.base_currency:
                            calculation.kiri_sute(
                                    api_wrapper.get_buy_order_gain(orderable), 8
                            ) if is_buy_order \
                            else - calculation.kiri_age(
                                    api_wrapper.get_sell_order_pay(orderable), 8
                            )
                    , api_wrapper.counter_currency:
                            - calculation.kiri_age(
                                    api_wrapper.get_buy_order_pay(counter_sum), 8
                            ) if is_buy_order \
                            else calculation.kiri_sute(
                                    api_wrapper.get_sell_order_gain(counter_sum), 8
                            )
            }

def get_order_plan_with_base_amount(api_wrapper, is_buy_order, order_amount):
    '''
    注文数から、約定を見込める(買い|売り)注文の一覧、各通貨の増減数量 を得る
    api_wrapper: 市場情報
    is_buy_order: 買い注文かどうか
    order_amount: 注文数
    '''
    # 注文一覧、取得数量、支払数量 の順序で返す
    return __get_order_plan(
            api_wrapper, is_buy_order, None, order_amount, __get_order_with_base_amount
    )

def get_order_plan_with_order(api_wrapper, is_buy_order, order_price, order_amount):
    '''
    注文から、約定を見込める(買い|売り)注文の一覧、各通貨の増減数量 を得る
    api_wrapper: 市場情報
    is_buy_order: 買い注文かどうか
    order_price: 注文価格
    order_amount: 注文数
    '''
    # 注文一覧、取得数量、支払数量 の順序で返す
    return __get_order_plan(
            api_wrapper, is_buy_order, order_price, order_amount, __get_order_with_order
    )

def __get_order_with_counter_amount(
        api_wrapper, price, amount, fraction, order_list, left_amount, base_sum
):
    '''
    相対通貨の数量から約定を見込める注文を得る
    api_wrapper: 市場情報
    price: 判定対象となる注文の価格
    amount: 判定対象となる注文の数量
    fraction: 前回注文までの最低注文数以下の注文数量合計
    order_list: 約定を見込める注文一覧
    left_amount: 残りの相対通貨数量
    base_sum: 基本通貨の取引数量(手数料未計算)
    '''
    # 最低注文数よりamountが少ない注文は、次の注文に含める
    if amount < api_wrapper.min_trade_amount:
        fraction = amount

    elif left_amount <= price * amount:
        # 残りの相対通貨が注文に収まった場合
        fraction = 0
        order_amount = calculation.kiri_sute(
                left_amount / price, api_wrapper.min_trade_unit
        )
        order_list.append([price, order_amount])
        base_sum += order_amount
        left_amount = 0

    else:
        # 残りの相対通貨が注文に収まらなかった場合
        fraction = 0
        order_list.append([price, amount])
        base_sum += amount
        left_amount -= price * amount

    return fraction, order_list, left_amount, base_sum

def get_order_plan_with_counter_amount(api_wrapper, is_buy_order, counter_amount):
    '''
    相対通貨の数量から、約定を見込める(買い|売り)注文の一覧、各通貨の増減数量 を得る
    api_wrapper: 市場情報
    is_buy_order: 買い注文かどうか
    counter_amount: 相対通貨の数量
    '''
    # APIよりdepthを取得し、
    # 発注する注文一覧、注文可能数量、基本通貨数量(手数料未計算)を得る
    fraction = 0
    order_list = []
    left_amount = counter_amount
    base_sum = 0
    for order in api_wrapper.get_sell_orders() if is_buy_order else api_wrapper.get_buy_orders():
        logger.debug('order=%s', order)
        price = api_wrapper.get_order_price(order)
        amount = fraction + api_wrapper.get_order_amount(order)

        if left_amount < price * api_wrapper.min_trade_amount:
            # 残りの相対通貨で最小単位の注文が出来ない場合
            break

        pre_fraction = fraction
        pre_base_sum = base_sum

        fraction, order_list, left_amount, base_sum = __get_order_with_counter_amount(
                api_wrapper, price, amount, fraction, order_list, left_amount, base_sum
        )
        logger.debug('fraction=%s, order_num=%s, left_amount=%s, base_sum=%s'
                , fraction, len(order_list), left_amount, base_sum
        )

        if base_sum == pre_base_sum and fraction == pre_fraction:
            # 注文が取得出来ない場合
            break

    # 注文一覧、注文可能数量、基本通貨数量(手数料未計算)
    orderable = counter_amount - left_amount
    logger.debug('order_list=%s, orderable=%s, base_sum=%s'
            , order_list, orderable, base_sum
    )

    # 注文一覧、各通貨の増減 の順序で返す
    return order_list \
            , {
                    api_wrapper.base_currency:
                            calculation.kiri_sute(
                                    api_wrapper.get_buy_order_gain(base_sum), 8
                            ) if is_buy_order \
                            else - calculation.kiri_age(
                                    api_wrapper.get_sell_order_pay(base_sum), 8
                            )
                    , api_wrapper.counter_currency:
                            - calculation.kiri_age(
                                    api_wrapper.get_buy_order_pay(orderable), 8
                            ) if is_buy_order \
                            else calculation.kiri_sute(
                                    api_wrapper.get_sell_order_gain(orderable), 8
                            )
            }

def get_balance(api_wrapper, public_key, secret_key):
    '''
    残高取得
    '''
    # 取引所API IF と引き当てる
    if api_wrapper.exchange_name == constants.MARKET_ALLCOIN:
        func = api_wrapper.account_info

    elif api_wrapper.exchange_name == constants.MARKET_BTCBOX:
        func = api_wrapper.account_balance

    elif api_wrapper.exchange_name == constants.MARKET_ETWINGS:
        func = api_wrapper.get_info

    # TODO: 結果を画一化して返却
    result = func(public_key, secret_key)
    logger.debug(result)

def order(api_wrapper, public_key, secret_key, is_buy_order, price, amount):
    '''
    発注
    '''
    # 取引所API IF と引き当てる
    if api_wrapper.exchange_name == constants.MARKET_ALLCOIN:
        func = api_wrapper.buy_coin if is_buy_order else api_wrapper.sell_coin

    elif api_wrapper.exchange_name == constants.MARKET_BTCBOX:
        func = api_wrapper.trade_add

    elif api_wrapper.exchange_name == constants.MARKET_ETWINGS:
        func = api_wrapper.trade

    # TODO: 結果を画一化して返却
    result = func(public_key, secret_key, is_buy_order, price, amount) \
            if not api_wrapper.exchange_name == constants.MARKET_ALLCOIN \
            else func(public_key, secret_key, price, amount)
    logger.debug(result)

def cancel_order(api_wrapper, public_key, secret_key, order):
    '''
    注文取消
    '''
    # 取引所API IF と引き当てる
    if api_wrapper.exchange_name == constants.MARKET_ALLCOIN:
        func = api_wrapper.cancel_order

    elif api_wrapper.exchange_name == constants.MARKET_BTCBOX:
        func = api_wrapper.trade_cancel

    elif api_wrapper.exchange_name == constants.MARKET_ETWINGS:
        func = api_wrapper.cancel_order

    # TODO: 結果を画一化して返却
    result = func(public_key, secret_key, order)
    logger.debug(result)
