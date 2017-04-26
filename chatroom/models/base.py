# -*- coding: utf8 -*-
from django_extensions.db.models import TimeStampedModel
from chatroom.base.util import cached_object
from chatroom.base.xredis import Redis
from chatroom.base import const
import cPickle as cjson
from playhouse.shortcuts import model_to_dict, dict_to_model


class CacheBase(object):
    """
    基类
    """
    OBJECT_KEY = '%(name)s:obj:%(oid)s'

    ENABLE_LOCAL_CACHE = False  # 启用内存缓存

    @classmethod
    @cached_object(lambda cls, oid: cls.OBJECT_KEY % ({
        'name': cls.__name__.lower(), 'oid': str(oid)}))
    def _load_object(cls, oid):
        obj = cls.objects.get(id=oid)
        return model_to_dict(obj)

    @classmethod
    def get_one(cls, oid, check_online=True):
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
        obj = dict_to_model(cls, obj)
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

    @classmethod
    def create_model(cls, **kwargs):
        ret = cls.objects.create(**kwargs)
        cls.clear_redis(ret.id)
        return ret.inserted_id

    @classmethod
    def update_model(cls, filters, data):
        ret = cls.objects.get(**filters).update(**data)
        cls.clear_redis(cls.id)
        obj = cls._load_object(str(ret.id))
        return obj

    @classmethod
    def delete_model(cls, **kwargs):
        obj = cls.objects.get(**kwargs)
        ret = cls.clear_redis(obj.id)
        return ret

    @classmethod
    def clear_redis(cls, oid):
        key = cls.OBJECT_KEY % ({'name': cls.__class__.__name__.lower(), 'oid': str(oid)})
        return Redis.delete(key)

    @property
    def offline(self):
        return self.status is None or self.status == const.OFFLINE

    def save(self, **kwargs):
        self.clear_redis(self.id)
        super(CacheBase, self).save(**kwargs)


class BaseModel(TimeStampedModel, CacheBase):
    pass
