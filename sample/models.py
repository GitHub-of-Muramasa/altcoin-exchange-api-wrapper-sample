# -*- encoding:UTF-8 -*-
import logging

from django.db import models

from utils.validators import UppercaseValidators

from api_wrapper import get_api_wrapper

logger = logging.getLogger(__name__)

'''
Created on 2015/02/11

@author: user

参考ソース。動きません。
'''
class Market(models.Model):
    '''
    市場情報
    '''
    # 交換所名
    exchange_name = models.CharField(max_length=16)

    # API使用可能間隔[秒]
    api_available_span = models.FloatField()

    # 基本通貨
    base_currency = models.CharField(max_length=5, validators=[UppercaseValidators()])

    # 相対通貨
    counter_currency = models.CharField(max_length=5, validators=[UppercaseValidators()])

    # 手数料[％]
    fee = models.FloatField()

    # 買い注文の手数料が取得数量に発生するか
    bid_fee_is_gain = models.BooleanField(default=True)

    # 売り注文の手数料が取得数量に発生するか
    ask_fee_is_gain = models.BooleanField(default=True)

    # 最小価格単位(小数点以下桁数の位)
    min_price_unit = models.SmallIntegerField()

    # 最低注文数
    min_trade_amount = models.FloatField()

    # 最小注文単位(小数点以下桁数の位)
    min_trade_unit = models.SmallIntegerField()

    # APIサポートクラス名
    api_util_class = models.CharField(max_length=32)

    class Meta:
        db_table = 'market'
        verbose_name = u'市場情報'

    def get_api_wrapper_instance(self):
        '''
        APIサポートクラスのインスタンスを得る
        '''
        return get_api_wrapper(self.api_util_class)(self)
