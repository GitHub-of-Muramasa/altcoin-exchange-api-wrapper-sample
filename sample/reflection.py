# -*- encoding:UTF-8 -*-
import logging

logger = logging.getLogger(__name__)

'''
Created on 2014/12/26

@author: user
'''
def class_for_name(module_name, class_name):
    '''
    stringのクラス名からクラスを得る
    '''
    import importlib

    # load the module, will raise ImportError if module cannot be loaded
    m = importlib.import_module(module_name)

    # get the class, will raise AttributeError if class cannot be found
    c = getattr(m, class_name)

    return c
