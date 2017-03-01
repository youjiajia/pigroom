# -*- coding: utf8 -*-
from redis import exceptions
from wanx.base.xredis import Redis
from wanx.base.util import (cached_object, cached_hash,
                            cached_set, cached_list, cached_zset)
from wanx.base.spam import Spam
from wanx.base.xpinyin import Pinyin
from wanx.models.xconfig import Config
from . import WanxTestCase

import cPickle as cjson
import json


class FunTestCase(WanxTestCase):
    """
    函数测试
    """
    STRING_KEY = 'test:string'
    HASH_KEY = 'test:hash'
    SET_KEY = 'test:set'
    LIST_KEY = 'test:list'
    ZSET_KEY = 'test:zset'

    @cached_object(STRING_KEY)
    def _cached_object(self, obj=None):
        return dict(obj)

    @cached_hash(HASH_KEY)
    def _cached_hash(self, d={}):
        return d

    @cached_set(SET_KEY)
    def _cached_set(self, s=()):
        return s

    @cached_list(LIST_KEY)
    def _cached_list(self, l=[]):
        return l

    @cached_zset(ZSET_KEY)
    def _cached_zset(self, zs=()):
        return zs

    def test_cached_object(self):
        self._cached_object()
        self.assertFalse(Redis.exists(self.STRING_KEY))
        self._cached_object({'test': 'OK'})
        self.assertEqual(cjson.loads(Redis.get(self.STRING_KEY)), {'test': 'OK'})

    def test_cached_hash(self):
        self._cached_hash()
        self.assertFalse(Redis.exists(self.HASH_KEY))
        self._cached_hash({'dog': 1, 'pig': 2})
        self.assertEqual(Redis.hget(self.HASH_KEY, 'dog'), '1')
        self.assertEqual(Redis.hget(self.HASH_KEY, 'pig'), '2')

    def test_cached_set(self):
        self._cached_set()
        self.assertEqual(Redis.get(self.SET_KEY), 'empty')
        with self.assertRaises(exceptions.ResponseError):
            Redis.sadd(self.SET_KEY, ('dog', 'pig'))
            Redis.delete(self.SET_KEY)
        self._cached_set(('dog', 'pig'))
        self.assertTrue(Redis.sismember(self.SET_KEY, 'dog'))
        self.assertTrue(Redis.sismember(self.SET_KEY, 'pig'))

    def test_cached_list(self):
        self._cached_list()
        self.assertEqual(Redis.get(self.LIST_KEY), 'empty')
        with self.assertRaises(exceptions.ResponseError):
            Redis.rpush(self.SET_KEY, ['dog', 'pig'])
            Redis.delete(self.SET_KEY)
        self._cached_list(['dog', 'pig'])
        self.assertListEqual(Redis.lrange(self.LIST_KEY, 0, -1), ['dog', 'pig'])

    def test_cached_zset(self):
        self._cached_zset()
        self.assertEqual(Redis.get(self.ZSET_KEY), 'empty')
        with self.assertRaises(exceptions.ResponseError):
            Redis.zadd(self.ZSET_KEY, 1, 'dog', 2, 'pig')
            Redis.delete(self.ZSET_KEY)
        self._cached_zset((1, 'dog', 2, 'pig'))
        self.assertListEqual(Redis.zrevrange(self.ZSET_KEY, 0, -1), ['pig', 'dog'])

    def test_spam(self):
        self.assertFalse(Spam.filter_words(u'不错'))
        self.assertTrue(Spam.filter_words(u'习近平'))
        self.assertEqual(Spam.replace_words(u'习近平是个好人'), '***是个好人')

    def test_pinyin(self):
        py = Pinyin()
        self.assertTrue(py.get_pinyin(u'习近平', ''), 'xijinping')

    def test_config(self):
        self.assertTrue(Config.fetch('no_key', 10, int), 10)
        self.assertTrue(Config.fetch('test_int', 10, int), 100)
        self.assertTrue(Config.fetch('test_str', 'error', str), 'test')
        self.assertTrue(Config.fetch('test_json', {}, json.loads), {'haha': 1, 'hehe': 2})
