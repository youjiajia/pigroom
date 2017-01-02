# -*- coding: utf8 -*-
from bson.objectid import ObjectId
from wanx.base.xmysql import MYDB
from wanx.base.xredis import Redis
from wanx.base.util import cached_object
from wanx.base import const

import cPickle as cjson
import datetime
import peewee as pw
import time


class ObjectDict(dict):
    """Makes a dictionary behave like an object, with attribute-style access.
    """

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            return None
            # raise AttributeError(name)

    def __setattr__(self, name, value):
        self[name] = value

    def __delattr__(self, name):
        try:
            del self[name]
        except KeyError:
            pass


class Document(ObjectDict):
    """
    基类
    """
    OBJECT_KEY = '%(name)s:obj:%(oid)s'

    ENABLE_LOCAL_CACHE = False  # 启用内存缓存

    @classmethod
    def init(cls):
        return cls({
            "create_at": time.time(),
        })

    @classmethod
    @cached_object(lambda cls, oid: cls.OBJECT_KEY % ({
        'name': cls.__name__.lower(), 'oid': str(oid)}))
    def _load_object(cls, oid):
        obj = cls.collection.find_one({'_id': ObjectId(str(oid))})
        return cls(obj)

    @classmethod
    def get_one(cls, oid, check_online=False):
        obj = None
        if not oid:
            return obj

        key = cls.OBJECT_KEY % ({'name': cls.__name__.lower(), 'oid': str(oid)})
        # 先从本地内存中获取
        if cls.ENABLE_LOCAL_CACHE and hasattr(cls, 'CACHED_OBJS'):
            obj = cls.CACHED_OBJS.get(key)

        # 从缓存中获取
        if not obj:
            obj = Redis.get(key)
            obj = cls(cjson.loads(obj)) if obj else cls._load_object(oid)
            # 存入本地内存
            if cls.ENABLE_LOCAL_CACHE and hasattr(cls, 'CACHED_OBJS') and obj:
                cls.CACHED_OBJS[key] = obj

        if not obj or (check_online and obj.offline):
            return None
        return obj

    @classmethod
    def get_list(cls, ids, check_online=True):
        if not ids:
            return []
        ret = list()
        # 使用mget方式一次性从缓存获取
        # keys = []
        # for _id in ids:
        #     key = cls.OBJECT_KEY % ({'name': cls.__name__.lower(), 'oid': str(_id)})
        #     keys.append(key)

        # objs = Redis.mget(keys)
        # for obj in objs:
        #     obj = cls(cjson.loads(obj)) if obj else cls.get_one(_id, check_online=check_online)
        #     if obj and not obj.offline:
        #         ret.append(obj)
        for _id in ids:
            obj = cls.get_one(_id, check_online=check_online)
            if obj:
                ret.append(obj)
        return ret

    def create_model(self):
        ret = self.collection.insert_one(self)
        return ret.inserted_id

    def update_model(self, data={}):
        data = data or self
        self.collection.update_one({'_id': self._id}, data)
        key = self.OBJECT_KEY % ({'name': self.__class__.__name__.lower(), 'oid': str(self._id)})
        Redis.delete(key)
        obj = self._load_object(str(self._id))
        return obj

    def delete_model(self):
        ret = self.collection.delete_one({"_id": ObjectId(self._id)})
        key = self.OBJECT_KEY % ({'name': self.__class__.__name__.lower(), 'oid': str(self._id)})
        Redis.delete(key)
        return ret.deleted_count

    @property
    def online(self):
        return self.status is None or self.status == const.ONLINE

    @property
    def offline(self):
        return not self.online

    def format(self):
        pass


class BaseModel(pw.Model):
    create_at = pw.DateTimeField(constraints=[pw.SQL('DEFAULT CURRENT_TIMESTAMP')],
                                 formats='%Y-%m-%d %H:%M:%S', verbose_name='创建时间')

    class Meta:
        database = MYDB

    def save(self, *args, **kwargs):
        if not self.create_at:
            self.create_at = datetime.datetime.now()
        return super(BaseModel, self).save(*args, **kwargs)
