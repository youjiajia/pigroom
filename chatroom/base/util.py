# -*- coding: utf8 -*-
from datetime import datetime
from flask import jsonify, request
from functools import wraps
from . import error

import cPickle as cjson
import functools
import random
import time
import hashlib
import os


def get_choices_desc(choices, value):
    for _value, _desc in choices:
        if value == _value:
            return _desc
    return None


def random_pick(sequence, key):
    if not sequence:
        return None

    total = sum([key(obj) if callable(key) else obj[key] for obj in sequence])
    if total < 0:
        return None

    rad = random.randint(1, total)

    cur_total = 0
    res = None
    for obj in sequence:
        cur_total += key(obj) if callable(key) else obj[key]
        if rad <= cur_total:
            res = obj
            break

    return res


def datetime2timestamp(dt):
    return time.mktime(dt.timetuple())


def str2timestamp(value):
    return time.mktime(time.strptime(value.strip(), "%Y-%m-%d %H:%M:%S"))


def timestamp2str(value):
    return datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M:%S')


def datetime2str(value):
    return datetime.fromtimestamp(value).strftime('%Y-%m-%d')


def hot_live_user_score(value, timestamp):
    return value * 1000000000 + (2411395200 - timestamp)


def get_md5(str):
    mymd5 = hashlib.md5()
    mymd5.update(str)
    return mymd5.hexdigest()


class Lockit(object):
    def __init__(self, cache, key, expire=5, mock=False):
        self._cache = cache
        self._key = key
        self._expire = expire
        self._mock = mock

    def __enter__(self):
        if self._mock:
            return False
        if self._cache.set(self._key, 1, ex=self._expire, nx=True):
            return False
        else:
            return True

    def __exit__(self, *args):
        if not self._mock:
            self._cache.delete(self._key)
        return True


def _cached_result(key_func, timeout=86400, snowslide=False, rtype='String'):
    """根据rtype参数选择相应的redis结构进行缓存
    rtype: String, Hash, Set, List, SortedSet
    """
    def wrapper(func):
        @wraps(func)
        def inner_func(*args):
            key = key_func(*args) if callable(key_func) else key_func
            result = None
            mock = not snowslide
            with Lockit(Redis, 'lock:%s' % (key), mock=mock) as locked:
                if locked:
                    time.sleep(0.5)
                else:
                    result = func(*args)
                    if rtype == 'Object' and result:
                        Redis.setex(key, timeout, cjson.dumps(result, 2))
                    elif rtype == 'Hash' and result:
                        Redis.hmset(key, result)
                        Redis.expire(key, timeout)
                    elif rtype == 'List':
                        Redis.delete(key)
                        # 处理结果为空数据, 防止穿透db, 在增加和查询的时候需要判断数据结构
                        Redis.rpush(key, *result) if result else Redis.set(key, 'empty')
                        Redis.expire(key, timeout)
                    elif rtype == 'Set':
                        Redis.delete(key)
                        # 处理结果为空数据, 防止穿透db, 在增加和查询的时候需要判断数据结构
                        Redis.sadd(key, *result) if result else Redis.set(key, 'empty')
                        Redis.expire(key, timeout)
                    elif rtype == 'SortedSet':
                        Redis.delete(key)
                        # 处理结果为空数据, 防止穿透db, 在增加和查询的时候需要判断数据结构
                        Redis.zadd(key, *result) if result else Redis.set(key, 'empty')
                        Redis.expire(key, timeout)
            return result
        return inner_func
    return wrapper

cached_object = functools.partial(_cached_result, rtype='Object')
cached_hash = functools.partial(_cached_result, rtype='Hash')
cached_set = functools.partial(_cached_result, rtype='Set')
cached_list = functools.partial(_cached_result, rtype='List')
cached_zset = functools.partial(_cached_result, rtype='SortedSet')
