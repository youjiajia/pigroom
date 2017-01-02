# -*- coding: utf-8 -*-
from redis import exceptions
from wanx.models import Document
from wanx.base.xmongo import DB
from wanx.base.xredis import Redis
from wanx.base import util


class Config(Document):
    """服务器参数配置
    title: 描述
    key: 名字
    value: 值
    """
    collection = DB.configs

    CONFIG_PREFIX = 'config:%s'

    def create_model(self):
        ret = super(Config, self).create_model()
        if ret:
            cache_key = self.CONFIG_PREFIX % (self.key)
            Redis.delete(cache_key)
        return ret

    def update_model(self, data={}):
        ret = super(Config, self).update_model(data)
        if ret:
            cache_key = self.CONFIG_PREFIX % (self.key)
            Redis.delete(cache_key)
            cache_key = self.CONFIG_PREFIX % (ret.key)
            Redis.delete(cache_key)
        return ret

    def delete_model(self):
        ret = super(Config, self).delete_model()
        if ret:
            cache_key = self.CONFIG_PREFIX % (self.key)
            Redis.delete(cache_key)
        return ret

    @classmethod
    def fetch(cls, key, default, func=None):
        try:
            cache_key = cls.CONFIG_PREFIX % (key)
            value = Redis.get(cache_key)
            if value is None:
                obj = cls.collection.find_one({'key': key})
                value = obj['value'] if obj else None
                if value:
                    Redis.setex(cache_key, 7 * 24 * 3600, value)

            if value is None:
                return default

            return apply(func, [value]) if callable(func) else value
        except:
            return default


class VersionConfig(Document):
    """版本管理
    """
    collection = DB.version_config

    ALL_VERSION_IDS = 'version:all'

    def create_model(self):
        _id = super(VersionConfig, self).create_model()
        if _id:
            key = self.ALL_VERSION_IDS
            Redis.delete(key)

        return _id

    def update_model(self, data={}):
        ret = super(VersionConfig, self).update_model(data)
        if ret:
            key = self.ALL_VERSION_IDS
            Redis.delete(key)

        return ret

    def delete_model(self):
        ret = super(VersionConfig, self).delete_model()
        if ret:
            key = self.ALL_VERSION_IDS
            Redis.delete(key)

        return ret

    @classmethod
    @util.cached_list(lambda cls: cls.ALL_VERSION_IDS, snowslide=True)
    def _load_all_version_ids(cls):
        channels = list(cls.collection.find({}, {'_id': 1}))
        _ids = [str(c['_id']) for c in channels]
        return _ids

    @classmethod
    def all_version_ids(cls):
        key = cls.ALL_VERSION_IDS
        if not Redis.exists(key):
            cls._load_all_version_ids()
        try:
            _ids = Redis.lrange(key, 0, -1)
        except exceptions.ResponseError:
            _ids = []
        return list(_ids)


class Province(Document):
    """省份管理
    """
    collection = DB.province

    ALL_PROVINCE_IDS = 'province:all'

    def create_model(self):
        _id = super(Province, self).create_model()
        if _id:
            key = self.ALL_PROVINCE_IDS
            Redis.delete(key)

        return _id

    def update_model(self, data={}):
        ret = super(Province, self).update_model(data)
        if ret:
            key = self.ALL_PROVINCE_IDS
            Redis.delete(key)

        return ret

    def delete_model(self):
        ret = super(Province, self).delete_model()
        if ret:
            key = self.ALL_PROVINCE_IDS
            Redis.delete(key)

        return ret

    @classmethod
    @util.cached_list(lambda cls: cls.ALL_PROVINCE_IDS, snowslide=True)
    def _load_all_province_ids(cls):
        province = list(cls.collection.find({}, {'_id': 1}))
        _ids = [str(p['_id']) for p in province]
        return _ids

    @classmethod
    def all_province_ids(cls):
        key = cls.ALL_PROVINCE_IDS
        if not Redis.exists(key):
            cls._load_all_province_ids()
        try:
            _ids = Redis.lrange(key, 0, -1)
        except exceptions.ResponseError:
            _ids = []
        return list(_ids)
