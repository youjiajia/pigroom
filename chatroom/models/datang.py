# -*- coding: utf8 -*-
from bson.objectid import ObjectId
from redis import exceptions
from urlparse import urljoin
from wanx.models import Document
from wanx.base.xredis import Redis
from wanx.base.xmongo import DB
from wanx.base import util, const
from wanx.base.cachedict import CacheDict
from wanx import app

import pymongo
import time


class DaTangVideo(Document):
    """视频
    """
    collection = DB.datang_videos

    CACHED_OBJS = CacheDict(max_len=100, max_age_seconds=5)

    GAME_HOTVIDEO_IDS = "dtvideos:hotgame:%(date)s:%(gid)s"  # 游戏人气视频队列
    USER_GAME_VIDEO_IDS = "dtvideos:user:%(uid)s:game:%(gid)s"  # 用户为某个游戏创建的视频队列

    def format(self, exclude_fields=[]):
        author_ex_fields = []
        game_ex_fields = []
        for field in exclude_fields:
            if field.startswith('author__'):
                _, _field = field.split('__')
                author_ex_fields.append(_field)
            elif field.startswith('game__'):
                _, _field = field.split('__')
                game_ex_fields.append(_field)

        vid = str(self._id)
        data = {
            'video_id': vid,
            'ratio': self.ratio,
            'title': self.title,
            'url': '%s/datang/videos/%s/play' % (app.config.get('SERVER_URL'), vid),
            'is_liked': False,
            'author': self.author,
            'cover': "%s%s" % (app.config.get("MEDIA_URL"), self.cover),
            'like_count': self.like,
            'create_at': self.create_at,
            'is_favored': False,
            'game': self.game,
            'comment_count': self.comment_count,
            'vv': self.vv,
            'duration': self.duration and int(self.duration),
            'tags': self.tags,
            'share_url': None,
            'status': self.status if self.status else None,
            'is_online': self.online
        }
        return data

    @property
    def online(self):
        _is_online = super(DaTangVideo, self).online
        return _is_online or self.status in [const.ELITE]

    def create_model(self):
        _id = super(DaTangVideo, self).create_model()
        if _id:
            if self.online:
                key = self.USER_GAME_VIDEO_IDS % ({'uid': str(self.author), 'gid': str(self.game)})
                try:
                    if Redis.exists(key):
                        Redis.zadd(key, self.create_at, str(_id))
                except exceptions.ResponseError:
                    Redis.delete(key)

        return _id

    def update_model(self, data={}):
        obj = super(DaTangVideo, self).update_model(data)
        if obj:
            # 下线-->上线
            if self.offline and obj.online:
                key = self.USER_GAME_VIDEO_IDS % ({'uid': str(self.author), 'gid': str(self.game)})
                try:
                    if Redis.exists(key):
                        Redis.zadd(key, self.create_at, str(self._id))
                except exceptions.ResponseError:
                    Redis.delete(key)

        return obj

    def delete_model(self):
        ret = super(DaTangVideo, self).delete_model()
        if ret:
            key = self.USER_GAME_VIDEO_IDS % ({'uid': str(self.author), 'gid': str(self.game)})
            try:
                Redis.zrem(key, str(self._id))
            except exceptions.ResponseError:
                Redis.delete(key)

        return ret

    def real_url(self):
        if self.url.lower().startswith('http://'):
            return self.url
        return urljoin(app.config.get('VIDEO_URL'), self.url)

    @classmethod
    def init(cls):
        doc = super(DaTangVideo, cls).init()
        doc.cover = 0
        doc.url = ''
        doc.like = 0
        doc.vv = 0
        doc.comment_count = 0
        doc.status = const.ONLINE
        return cls(doc)

    @classmethod
    @util.cached_list(lambda cls, gid: cls.GAME_HOTVIDEO_IDS % ({'date': time.strftime("%Y%m%d"),
                                                                 'gid': gid}),
                      timeout=86400, snowslide=True)
    def _load_game_hotvideo_ids(cls, gid):
        videos = list(cls.collection.find(
            {
                'game': ObjectId(gid),
                'create_at': {'$gte': int(time.time()) - const.POPULAR_VIDEO.get("time_range")},
                '$or': [{'status': {'$exists': False}},
                        {'status': {'$in': [const.ONLINE, const.ELITE]}}]
            },
            {'_id': 1, 'vv': 1}
        ).sort("vv", pymongo.DESCENDING))

        if len(videos) < const.POPULAR_VIDEO.get("max_video_num", 30):
            videos = list(cls.collection.find(
                {
                    'game': gid,
                    'create_at': {'$gte': int(time.time()) - 30 * 24 * 60 * 60},
                    '$or': [{'status': {'$exists': False}},
                            {'status': {'$in': [const.ONLINE, const.ELITE]}}]
                },
                {'_id': 1, 'vv': 1}
            ).sort("vv", pymongo.DESCENDING))

        vids = [v['_id'] for v in videos]
        return vids

    @classmethod
    def game_hotvideo_ids(cls, gid, page, pagesize, maxs=None):
        key = cls.GAME_HOTVIDEO_IDS % ({'date': time.strftime("%Y%m%d"), 'gid': gid})
        if not Redis.exists(key):
            cls._load_game_hotvideo_ids(gid)
        try:
            start = (page - 1) * pagesize if page else 0
            stop = (start + pagesize - 1) if pagesize else -1
            ids = Redis.lrange(key, start, stop)
        except exceptions.ResponseError:
            ids = []
        return list(ids)

    @classmethod
    @util.cached_zset(lambda cls, uid, gid: cls.USER_GAME_VIDEO_IDS % ({'uid': uid, 'gid': gid}))
    def _load_user_game_video_ids(cls, uid, gid):
        videos = list(cls.collection.find(
            {
                'author': uid,
                'game': gid,
                '$or': [{'status': {'$exists': False}},
                        {'status': {'$in': [const.ONLINE, const.ELITE]}}]
            },
            {'_id': 1, 'create_at': 1}
        ).sort("create_at", pymongo.DESCENDING))
        ret = list()
        for i in videos:
            ret.extend([i['create_at'], str(i['_id'])])
        return tuple(ret)

    @classmethod
    def user_game_video_ids(cls, uid, gid, page=None, pagesize=None, maxs=None):
        key = cls.USER_GAME_VIDEO_IDS % ({'uid': uid, 'gid': gid})
        if not Redis.exists(key):
            cls._load_user_game_video_ids(uid, gid)
        try:
            if maxs:
                ids = Redis.zrevrangebyscore(key, '(%.6f' % (maxs), '-inf', start=0, num=pagesize)
            else:
                start = (page - 1) * pagesize
                stop = start + pagesize - 1
                ids = Redis.zrevrange(key, start, stop)
        except exceptions.ResponseError:
            ids = []
        return list(ids)
