# -*- encoding:UTF-8 -*-
import logging, re

logger = logging.getLogger(__name__)

'''
Created on 2014/12/08

@author: user
'''
def __round_framework(func, m, n=0):
    '''
    四捨五入、切り上げ、切り捨て で共通する処理
    '''
    # 小数点以下桁数指定をint型にする
    n = int(n)

    # m の絶対値を処理対象とする
    m_str = str(abs(m))

    # X.Xe-nn 表記かをチェック
    pattern = re.compile('(\d+\.\d+)[eE]-(\d+)')
    obj = pattern.match(m_str)
    if obj:
        # X.Xe-nn 表記の場合
        # 0.00･･･ 表記に変更する
        m_str = '0.' + ''.center(int(obj.group(2)) - 1, '0') \
                + obj.group(1).replace('.', '')
        logger.debug(m_str)

    # 整数部分と小数部分に分ける
    m_str = m_str.split('.')

    if 1 < len(m_str) and 0 <= n < len(m_str[1]):
        # 小数部分が存在し、小数点以下桁数指定が有効な場合
        # 個別処理
        result = func(m_str, n)

        if m < 0:
            # m が負の数である場合
            # マイナスを掛けて正負を元に戻す
            result = -1 * result

    else:
        # 小数点以下桁数指定が無効な場合
        if n < 0:
            # 負の数が指定された場合
            raise RuntimeError, u"小数点以下桁数には正の整数を指定してください。"

        # それ以外は値をそのまま返す
        result = m

    return result

def __kiri_age(m_str, n):
    '''
    切り上げ の個別処理
    '''
    if n == 0:
        # 整数部を切り上げる
        result = int(m_str[0]) + 1
    else:
        # 小数点以下桁数の指定部分に1を加算し、残りの桁は捨てる
        result = int(m_str[0]) + 10**(-n) * (int(m_str[1][:n]) + 1)

    return result

def __kiri_sute(m_str, n):
    '''
    切り捨て の個別処理
    '''
    if n == 0:
        # 小数点以下を切り捨てる
        result = int(m_str[0])
    else:
        # 小数点以下桁数の指定部分より下の桁を切り捨てる
        result = int(m_str[0]) + 10**(-n) * int(m_str[1][:n])

    return result

def __shisha_gonyu(m_str, n):
    '''
    四捨五入 の個別処理
    '''
    if int(m_str[1][n]) >= 5:
        # 切り上げ
        result = __kiri_age(m_str, n)

    else:
        # 切り捨て
        result = __kiri_sute(m_str, n)

    return result

def shisha_gonyu(m, n=0):
    '''
    四捨五入を行う
    '''
    return __round_framework(__shisha_gonyu, m, n)

def kiri_age(m, n=0):
    '''
    切り上げ処理を行う
    '''
    return __round_framework(__kiri_age, m, n)

def kiri_sute(m, n=0):
    '''
    切り捨て処理を行う
    '''
    return __round_framework(__kiri_sute, m, n)