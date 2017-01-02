# -*- coding: utf8 -*-
from bson.objectid import ObjectId
from flask import request
from redis import exceptions
from urlparse import urljoin
from wanx.models import Document
from wanx.base.xredis import Redis
from wanx.base.xmongo import DB
from wanx.base import util, const
from wanx.base.cachedict import CacheDict
from wanx.base.log import print_log
from wanx import app

import pymongo
import time
import json

from wanx.platforms import Xlive


class Video(Document):
    """视频
    """
    collection = DB.videos

    CACHED_OBJS = CacheDict(max_len=100, max_age_seconds=5)

    GAME_VIDEO_IDS = "videos:game:%(gid)s"  # 游戏所有视频队列(<30除外)
    GAME_HOTVIDEO_IDS = "videos:hotgame:%(date)s:%(gid)s"  # 游戏人气视频队列
    USER_VIDEO_IDS = "videos:user:%(uid)s"  # 用户创建视频队列
    USER_LIVE_VIDEO_IDS = "videos:live:user:%(uid)s"  # 用户直播转录播视频队列
    USER_GAME_VIDEO_IDS = "videos:user:%(uid)s:game:%(gid)s"  # 用户为某个游戏创建的视频队列
    LATEST_VIDEO_IDS = "videos:latest"  # 最新视频队列
    ELITE_VIDEO_IDS = "videos:elite"  # 精选视频队列
    GAME_ELITE_VIDEO_IDS = "videos:elite:game:%(gid)s"  # 某个游戏的精选视频队列

    def format(self, exclude_fields=[]):
        from wanx.models.user import User
        from wanx.models.game import Game
        game = Game.get_one(str(self.game), check_online=False)
        author = User.get_one(str(self.author), check_online=False)
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
        _share_uri = '/page/html/share.html?game_id=%s&video_id=%s' % (str(self.game), vid)
        share_url = urljoin(app.config.get('SHARE_URL'), _share_uri)
        # share_url = urljoin(app.config.get('SHARE_URL'), '/share/page/%s' % (vid))

        from wanx.models.activity import ActivityVideo
        vlv = ActivityVideo.get_activity_video_by_vid(vid)
        if vlv:
            activity_id = vlv.activity_id

            from wanx.models.activity import ActivityConfig
            activity = ActivityConfig.get_one(str(activity_id))
            others_video_share_title = activity.others_video_share_title
            self_video_share_title = activity.self_video_share_title
        else:
            from wanx.models.home import Share
            share = Share.get_by_others_video()
            share_self = Share.get_by_self_video()
            others_video_share_title = share.title if share else None
            self_video_share_title = share_self.title if share_self else None

        ut = request.values.get("ut", None)
        uid = User.uid_from_token(ut)

        auth = str(self.author)

        share_title = None
        if auth == uid:
            share_title = self_video_share_title
        else:
            share_title = others_video_share_title

        data = {
            'video_id': vid,
            'ratio': self.ratio,
            'title': self.title,
            'url': '%s/videos/%s/play' % (app.config.get('SERVER_URL'), vid),
            'is_liked': False,
            'author': author and author.format(exclude_fields=author_ex_fields),
            'cover': urljoin(app.config.get("MEDIA_URL"), self.cover),
            'like_count': self.like,
            'create_at': self.create_at,
            'is_favored': False,
            'game': game and game.format(exclude_fields=game_ex_fields),
            'comment_count': self.comment_count,
            'gift_count': self.gift_count or 0,
            'gift_num': self.gift_num or 0,
            'vv': self.vv,
            'duration': self.duration and int(self.duration),
            'tags': self.tags,
            'share_url': share_url,
            'status': self.status if self.status else None,
            'is_online': self.online,
            'event_id': self.event_id or None,
            'share_title': share_title
        }

        uid = request.authed_user and str(request.authed_user._id)
        if 'is_favored' not in exclude_fields:
            data['is_favored'] = vid in UserFaverVideo.faver_video_ids(uid) if uid else False
        if 'is_liked' not in exclude_fields:
            is_liked = False
            if uid and UserLikeVideo.get_by_ship(uid, str(self._id)):
                is_liked = True
            data['is_liked'] = is_liked
        return data

    @property
    def online(self):
        _is_online = super(Video, self).online
        return _is_online or self.status in [const.ELITE]

    def create_model(self):
        # 设置发不精华时间
        if self.status == const.ELITE:
            self.release_time = self.release_time or time.time()
        _id = super(Video, self).create_model()
        if _id:
            if self.status == const.ELITE:
                key = self.ELITE_VIDEO_IDS
                try:
                    Redis.zadd(key, self.release_time, str(self._id))
                except exceptions.ResponseError:
                    Redis.delete(key)

            if self.online:
                # 更新游戏下视频数量
                from wanx.models.game import Game
                game = Game.get_one(str(self.game), check_online=False)
                game.update_model({'$inc': {'video_count': 1}})

                # 更新用户创建视频数量
                from wanx.models.user import User
                user = User.get_one(str(self.author), check_online=False)
                user.update_model({'$inc': {'video_count': 1}})

                key = self.GAME_VIDEO_IDS % ({'gid': str(self.game)})
                try:
                    if Redis.exists(key) and self.duration >= const.DURATION:
                        Redis.zadd(key, self.create_at, str(_id))
                except exceptions.ResponseError:
                    Redis.delete(key)

                key = self.USER_VIDEO_IDS % ({'uid': str(self.author)})
                try:
                    if Redis.exists(key):
                        Redis.zadd(key, self.create_at, str(_id))
                except exceptions.ResponseError:
                    Redis.delete(key)

                if self.event_id:
                    key = self.USER_LIVE_VIDEO_IDS % ({'uid': str(self.author)})
                    try:
                        if Redis.exists(key):
                            Redis.zadd(key, self.create_at, str(_id))
                    except exceptions.ResponseError:
                        Redis.delete(key)

                key = self.USER_GAME_VIDEO_IDS % ({'uid': str(self.author), 'gid': str(self.game)})
                try:
                    if Redis.exists(key):
                        Redis.zadd(key, self.create_at, str(_id))
                except exceptions.ResponseError:
                    Redis.delete(key)

                key = self.LATEST_VIDEO_IDS
                try:
                    if Redis.exists(key) and self.duration >= const.DURATION:
                        Redis.zadd(key, self.create_at, str(_id))
                except exceptions.ResponseError:
                    Redis.delete(key)

        return _id

    def update_model(self, data={}):
        from_status = self.status
        to_status = data['$set'].get('status', from_status) if '$set' in data else from_status
        # 发布到精选区, 设置发布时间(release_time)
        if to_status != from_status and to_status == const.ELITE:
            data['$set']['release_time'] = data['$set']['release_time'] or time.time()
        obj = super(Video, self).update_model(data)
        if obj:
            # 精选视频-->非精选视频
            if to_status != from_status and from_status == const.ELITE:
                key = self.ELITE_VIDEO_IDS
                try:
                    Redis.zrem(key, str(self._id))
                except exceptions.ResponseError:
                    Redis.delete(key)

                key = self.GAME_ELITE_VIDEO_IDS % ({'gid': str(self.game)})
                try:
                    Redis.zrem(key, str(self._id))
                except exceptions.ResponseError:
                    Redis.delete(key)
            # 非精选视频-->精选视频
            elif to_status != from_status and to_status == const.ELITE:
                key = self.ELITE_VIDEO_IDS
                try:
                    Redis.zadd(key, obj.release_time, str(self._id))
                except exceptions.ResponseError:
                    Redis.delete(key)

                key = self.GAME_ELITE_VIDEO_IDS % ({'gid': str(self.game)})
                try:
                    Redis.zadd(key, obj.release_time, str(self._id))
                except exceptions.ResponseError:
                    Redis.delete(key)

            # 上线-->下线
            if self.online and obj.offline:
                # 更新游戏下视频数量
                from wanx.models.game import Game
                game = Game.get_one(str(self.game), check_online=False)
                game.update_model({'$inc': {'video_count': -1}})

                # 更新用户创建视频数量
                from wanx.models.user import User
                user = User.get_one(str(self.author), check_online=False)
                user.update_model({'$inc': {'video_count': -1}})

                # 异步更新用户收藏视频数
                from wanx.base.xgearman import Gearman
                data = dict(action='offline', vid=str(self._id))
                data = json.dumps(data)
                try:
                    Gearman().do_background('modify_video', data)
                except:
                    print_log('gearman', 'do background error')

                # 视频下线删除已参赛作品
                from wanx.models.activity import ActivityVideo
                activity_videos = ActivityVideo.get_activity_video(vid=str(self._id))
                for a in activity_videos:
                    a = ActivityVideo.get_one(a["_id"], check_online=False)
                    a.delete_model()

            # 下线-->上线
            if self.offline and obj.online:
                # 更新游戏下视频数量
                from wanx.models.game import Game
                game = Game.get_one(str(self.game), check_online=False)
                game.update_model({'$inc': {'video_count': 1}})

                # 更新用户创建视频数量
                from wanx.models.user import User
                user = User.get_one(str(self.author), check_online=False)
                user.update_model({'$inc': {'video_count': 1}})

                # 异步更新用户收藏视频数
                from wanx.base.xgearman import Gearman
                data = dict(action='online', vid=str(self._id))
                data = json.dumps(data)
                try:
                    Gearman().do_background('modify_video', data)
                except:
                    print_log('gearman', 'do background error')

                key = self.GAME_VIDEO_IDS % ({'gid': str(self.game)})
                try:
                    if Redis.exists(key) and self.duration >= const.DURATION:
                        Redis.zadd(key, self.create_at, str(self._id))
                except exceptions.ResponseError:
                    Redis.delete(key)

                key = self.USER_VIDEO_IDS % ({'uid': str(self.author)})
                try:
                    if Redis.exists(key):
                        Redis.zadd(key, self.create_at, str(self._id))
                except exceptions.ResponseError:
                    Redis.delete(key)

                if self.event_id:
                    key = self.USER_LIVE_VIDEO_IDS % ({'uid': str(self.author)})
                    try:
                        if Redis.exists(key):
                            Redis.zadd(key, self.create_at, str(self._id))
                    except exceptions.ResponseError:
                        Redis.delete(key)

                key = self.USER_GAME_VIDEO_IDS % ({'uid': str(self.author), 'gid': str(self.game)})
                try:
                    if Redis.exists(key):
                        Redis.zadd(key, self.create_at, str(self._id))
                except exceptions.ResponseError:
                    Redis.delete(key)

                key = self.LATEST_VIDEO_IDS
                try:
                    if Redis.exists(key) and self.duration >= const.DURATION:
                        Redis.zadd(key, self.create_at, str(self._id))
                except exceptions.ResponseError:
                    Redis.delete(key)
        return obj

    def delete_model(self):
        ret = super(Video, self).delete_model()
        if ret:
            if self.online:
                # 更新游戏下视频数量
                from wanx.models.game import Game
                game = Game.get_one(str(self.game), check_online=False)
                game.update_model({'$inc': {'video_count': -1}})

                # 更新用户创建视频数量
                from wanx.models.user import User
                user = User.get_one(str(self.author), check_online=False)
                user.update_model({'$inc': {'video_count': -1}})

                # 异步更新用户收藏视频数
                from wanx.base.xgearman import Gearman
                data = dict(action='offline', vid=str(self._id))
                data = json.dumps(data)
                try:
                    Gearman().do_background('modify_video', data)
                except:
                    print_log('gearman', 'do background error')

            key = self.GAME_VIDEO_IDS % ({'gid': str(self.game)})
            try:
                Redis.zrem(key, str(self._id))
            except exceptions.ResponseError:
                Redis.delete(key)

            key = self.USER_VIDEO_IDS % ({'uid': str(self.author)})
            try:
                Redis.zrem(key, str(self._id))
            except exceptions.ResponseError:
                Redis.delete(key)

            if self.event_id:
                key = self.USER_LIVE_VIDEO_IDS % ({'uid': str(self.author)})
                try:
                    Redis.zrem(key, str(self._id))
                except exceptions.ResponseError:
                    Redis.delete(key)

            key = self.USER_GAME_VIDEO_IDS % ({'uid': str(self.author), 'gid': str(self.game)})
            try:
                Redis.zrem(key, str(self._id))
            except exceptions.ResponseError:
                Redis.delete(key)

            key = self.LATEST_VIDEO_IDS
            try:
                Redis.zrem(key, str(self._id))
            except exceptions.ResponseError:
                Redis.delete(key)

            key = self.ELITE_VIDEO_IDS
            try:
                Redis.zrem(key, str(self._id))
            except exceptions.ResponseError:
                Redis.delete(key)

            key = self.GAME_ELITE_VIDEO_IDS % ({'gid': str(self.game)})
            try:
                Redis.zrem(key, str(self._id))
            except exceptions.ResponseError:
                Redis.delete(key)

            # 删除已参赛作品
            from wanx.models.activity import ActivityVideo
            activity_videos = ActivityVideo.get_activity_video(vid=str(self._id))
            for a in activity_videos:
                a = ActivityVideo.get_one(str(a["_id"]))
                a.delete_model()

        return ret

    def real_url(self):
        if self.url.lower().startswith('http://'):
            return self.url
        return urljoin(app.config.get('VIDEO_URL'), self.url)

    @classmethod
    def init(cls):
        doc = super(Video, cls).init()
        doc.cover = ''
        doc.url = ''
        doc.like = 0
        doc.vv = 0
        doc.comment_count = 0
        doc.gift_count = 0
        doc.gift_num = 0
        doc.status = const.ONLINE
        return cls(doc)

    @classmethod
    def search(cls, keyword):
        ids = cls.collection.find(
            {
                'duration': {'$gte': const.DURATION},
                'title': {'$regex': keyword, '$options': 'i'}
            },
            {'_id': 1}
        ).sort("create_at", pymongo.DESCENDING)
        ids = [_id['_id'] for _id in ids]
        return list(ids) if ids else list()

    @classmethod
    @util.cached_zset(lambda cls, gid: cls.GAME_VIDEO_IDS % ({'gid': gid}), snowslide=True)
    def _load_game_video_ids(cls, gid):
        videos = list(cls.collection.find(
            {
                'game': ObjectId(gid),
                'duration': {'$gte': const.DURATION},
                '$or': [{'status': {'$exists': False}},
                        {'status': {'$in': [const.ONLINE, const.ELITE]}}]
            },
            {'_id': 1, 'create_at': 1}
        ).sort("create_at", pymongo.DESCENDING))
        ret = list()
        for v in videos:
            ret.extend([v['create_at'], str(v['_id'])])
        return tuple(ret)

    @classmethod
    def game_video_ids(cls, gid, page, pagesize, maxs=None):
        key = cls.GAME_VIDEO_IDS % ({'gid': gid})
        if not Redis.exists(key):
            cls._load_game_video_ids(gid)
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

    @classmethod
    def game_video_count(cls, gid):
        key = cls.GAME_VIDEO_IDS % ({'gid': gid})
        if not Redis.exists(key):
            cls._load_game_video_ids(gid)
        try:
            count = Redis.zcard(key)
        except exceptions.ResponseError:
            count = 0
        return count

    @classmethod
    @util.cached_list(lambda cls, gid: cls.GAME_HOTVIDEO_IDS % ({'date': time.strftime("%Y%m%d"),
                                                                 'gid': gid}),
                      timeout=86400, snowslide=True)
    def _load_game_hotvideo_ids(cls, gid):
        videos = list(cls.collection.find(
            {
                'game': ObjectId(gid),
                'duration': {'$gte': const.DURATION},
                'create_at': {'$gte': int(time.time()) - const.POPULAR_VIDEO.get("time_range")},
                '$or': [{'status': {'$exists': False}},
                        {'status': {'$in': [const.ONLINE, const.ELITE]}}]
            },
            {'_id': 1, 'vv': 1}
        ).sort("vv", pymongo.DESCENDING).limit(const.POPULAR_VIDEO.get("max_video_num")))

        if len(videos) < const.POPULAR_VIDEO.get("max_video_num", 30):
            videos = list(cls.collection.find(
                {
                    'game': ObjectId(gid),
                    'duration': {'$gte': const.DURATION},
                    'create_at': {'$gte': int(time.time()) - 30 * 24 * 60 * 60},
                    '$or': [{'status': {'$exists': False}},
                            {'status': {'$in': [const.ONLINE, const.ELITE]}}]
                },
                {'_id': 1, 'vv': 1}
            ).sort("vv", pymongo.DESCENDING).limit(const.POPULAR_VIDEO.get("max_video_num")))

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
    @util.cached_zset(lambda cls, uid: cls.USER_VIDEO_IDS % ({'uid': uid}))
    def _load_user_video_ids(cls, uid):
        videos = list(cls.collection.find(
            {
                'author': ObjectId(uid),
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
    def user_video_ids(cls, uid, page=None, pagesize=None, maxs=None):
        key = cls.USER_VIDEO_IDS % ({'uid': uid})
        if not Redis.exists(key):
            cls._load_user_video_ids(uid)
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

    @classmethod
    @util.cached_zset(lambda cls, uid: cls.USER_LIVE_VIDEO_IDS % ({'uid': uid}))
    def _load_user_live_video_ids(cls, uid):
        videos = list(cls.collection.find(
            {
                'author': ObjectId(uid),
                'event_id': {'$exists': True},
                '$or': [{'status': {'$exists': False}},
                        {'status': {'$in': [const.ONLINE, const.ELITE]}}]
            },
            {'_id': 1, 'create_at': 1}
        ))
        ret = list()
        for i in videos:
            ret.extend([i['create_at'], str(i['_id'])])
        return tuple(ret)

    @classmethod
    def user_live_video_ids(cls, uid, page=None, pagesize=None, maxs=None):
        key = cls.USER_LIVE_VIDEO_IDS % ({'uid': uid})
        if not Redis.exists(key):
            cls._load_user_live_video_ids(uid)
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

    @classmethod
    def user_video_count(cls, uid):
        key = cls.USER_VIDEO_IDS % ({'uid': uid})
        if not Redis.exists(key):
            cls._load_user_video_ids(uid)
        try:
            count = Redis.zcard(key)
        except exceptions.ResponseError:
            count = 0
        return count

    @classmethod
    @util.cached_zset(lambda cls, uid, gid: cls.USER_GAME_VIDEO_IDS % ({'uid': uid, 'gid': gid}))
    def _load_user_game_video_ids(cls, uid, gid):
        videos = list(cls.collection.find(
            {
                'author': ObjectId(uid),
                'game': ObjectId(gid),
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

    @classmethod
    @util.cached_zset(LATEST_VIDEO_IDS, snowslide=True)
    def _load_latest_video_ids(cls):
        # 后台配置视频筛选条件, 默认条件: 有效时长(30s) 播放量(0)
        from wanx.models.xconfig import Config
        vv = Config.fetch('latest_video_vv', 0, int)
        duration = Config.fetch('latest_video_duration', 30, int)

        videos = list(cls.collection.find(
            {
                'vv': {'$gte': vv},
                'duration': {'$gte': duration},
                '$or': [{'status': {'$exists': False}},
                        {'status': {'$in': [const.ONLINE, const.OFFLINE, const.ELITE]}}]
            },
            {'_id': 1, 'create_at': 1}
        ).sort("create_at", pymongo.DESCENDING).limit(2000))
        ret = list()
        for i in videos:
            ret.extend([i['create_at'], str(i['_id'])])
        return tuple(ret)

    @classmethod
    def latest_video_ids(cls, page, pagesize, maxs=None):
        key = cls.LATEST_VIDEO_IDS
        if not Redis.exists(key):
            cls._load_latest_video_ids()
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

    @classmethod
    @util.cached_zset(lambda cls: cls.ELITE_VIDEO_IDS, snowslide=True)
    def _load_elite_video_ids(cls):
        videos = list(cls.collection.find(
            {
                'status': const.ELITE,
            },
            {'_id': 1, 'release_time': 1}
        ).sort("release_time", pymongo.DESCENDING).limit(2000))
        ret = list()
        for v in videos:
            if 'release_time' in v:
                ret.extend([v['release_time'], str(v['_id'])])
        return tuple(ret)

    @classmethod
    def elite_video_ids(cls, page, pagesize, maxs=None):
        key = cls.ELITE_VIDEO_IDS
        if not Redis.exists(key):
            cls._load_elite_video_ids()
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

    @classmethod
    @util.cached_zset(lambda cls, gid: cls.GAME_ELITE_VIDEO_IDS % ({'gid': gid}), snowslide=True)
    def _load_game_elite_video_ids(cls, gid):
        videos = list(cls.collection.find(
            {
                'game': ObjectId(gid),
                'status': const.ELITE,
            },
            {'_id': 1, 'release_time': 1}
        ).sort("release_time", pymongo.DESCENDING))
        ret = list()
        for v in videos:
            if 'release_time' in v:
                ret.extend([v['release_time'], str(v['_id'])])
        return tuple(ret)

    @classmethod
    def game_elite_video_ids(cls, gid, page, pagesize, maxs=None):
        key = cls.GAME_ELITE_VIDEO_IDS % ({'gid': gid})
        if not Redis.exists(key):
            cls._load_game_elite_video_ids(gid)
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

    @classmethod
    def users_video_ids(cls, uids, gid=None, page=None, pagesize=None, maxs=None):
        start = (page - 1) * pagesize
        cond = {
            'author': {'$in': uids},
            '$or': [{'status': {'$exists': False}},
                    {'status': {'$in': [const.ONLINE, const.ELITE]}}]
        }
        if maxs:
            start = 0
            cond.update({'create_at': {'$lt': maxs}})
        if gid:
            cond.update({'game': ObjectId(gid)})
        videos = list(cls.collection.find(
            cond,
            {'_id': 1}
        ).sort("create_at", pymongo.DESCENDING).limit(pagesize).skip(start))
        vids = [str(v['_id']) for v in videos]
        return vids

    @classmethod
    def users_video_count(cls, uids, gid=None):
        cond = {
            'author': {'$in': uids},
            '$or': [{'status': {'$exists': False}},
                    {'status': {'$in': [const.ONLINE, const.ELITE]}}]
        }
        if gid:
            cond.update({'game': ObjectId(gid)})
        count = cls.collection.find(cond).count()
        return count or 0

    @classmethod
    def games_video_ids(cls, gids, page, pagesize, maxs=None):
        if maxs:
            videos = list(cls.collection.find(
                {
                    'game': {'$in': gids},
                    'create_at': {'$lte': maxs},
                    '$or': [{'status': {'$exists': False}},
                            {'status': {'$in': [const.ONLINE, const.ELITE]}}]
                },
                {'_id': 1}
            ).sort("create_at", pymongo.DESCENDING).limit(pagesize))
        else:
            start = (page - 1) * pagesize
            videos = list(cls.collection.find(
                {
                    'game': {'$in': gids},
                    '$or': [{'status': {'$exists': False}},
                            {'status': {'$in': [const.ONLINE, const.ELITE]}}]
                },
                {'_id': 1}
            ).sort("create_at", pymongo.DESCENDING).limit(pagesize).skip(start))
        vids = [str(v['_id']) for v in videos]
        return vids

    @classmethod
    def activity_video_ids(cls, uid, pagesize, page, gids=[], activity_config={}):
        # 获取可参赛视频(符合活动条件并且未参赛)
        begin_at = activity_config.get('begin_at', time.time())
        end_at = activity_config.get('end_at', time.time())
        duration = activity_config.get('video_duration', 0)
        start = (page - 1) * pagesize
        cond = {
            'author': ObjectId(uid),
            'create_at': {'$gte': begin_at, '$lte': end_at},
            'duration': {'$gte': duration},
            '$and': [
                {'$or': [
                    {'status': {'$exists': False}},
                    {'status': {'$in': [const.ONLINE, const.ELITE]}}
                ]},
                {'$or': [
                    {'activity_ids': {'$exists': False}},
                    {'activity_ids': []}
                ]}
            ]
        }

        if gids:
            cond.update({'game': {'$in': gids}})

        videos = list(cls.collection.find(cond)
                      .sort('create_at', pymongo.DESCENDING).limit(pagesize).skip(start))
        vids = [v['_id'] for v in videos]
        return vids

    @classmethod
    def get_video_by_event_id(cls, eid, uid=None):
        cond = {'event_id': eid}
        if uid:
            cond.update({'author': ObjectId(uid)})

        video = cls.collection.find_one(cond, {'event_id': 1, '_id': 1})
        return video["_id"] if video else None


class UserFaverVideo(Document):
    """用户收藏的视频
    """
    collection = DB.favor_video

    FAVER_VIDEO_IDS = "videos:ufav:%(uid)s"  # 用户收藏视频队列

    def create_model(self):
        _id = super(UserFaverVideo, self).create_model()
        if _id:
            # 更新用户收藏视频数量
            from wanx.models.user import User
            user = User.get_one(str(self.source), check_online=False)
            user.update_model({'$inc': {'favor_count': 1}})

            key = self.FAVER_VIDEO_IDS % ({'uid': str(self.source)})
            try:
                if Redis.exists(key):
                    Redis.zadd(key, self.create_at, str(self.target))
            except exceptions.ResponseError:
                Redis.delete(key)
        return _id

    def delete_model(self):
        ret = super(UserFaverVideo, self).delete_model()
        if ret:
            # 更新用户收藏视频数量
            from wanx.models.user import User
            user = User.get_one(str(self.source), check_online=False)
            user.update_model({'$inc': {'favor_count': -1}})

            key = self.FAVER_VIDEO_IDS % ({'uid': str(self.source)})
            try:
                Redis.zrem(key, str(self.target))
            except exceptions.ResponseError:
                Redis.delete(key)
        return ret

    @classmethod
    def init(cls):
        doc = super(UserFaverVideo, cls).init()
        return cls(doc)

    @classmethod
    def get_by_ship(cls, sid, tid):
        ufv = cls.collection.find_one({
            'source': ObjectId(sid),
            'target': ObjectId(tid)
        })
        return cls(ufv) if ufv else None

    @classmethod
    @util.cached_zset(lambda cls, uid: cls.FAVER_VIDEO_IDS % ({'uid': uid}))
    def _load_faver_video_ids(cls, uid):
        videos = list(cls.collection.find(
            {'source': ObjectId(uid)},
            {'target': 1, 'create_at': 1}
        ).sort("create_at", pymongo.DESCENDING))
        ret = list()
        for v in videos:
            if Video.get_one(str(v['target'])):
                ret.extend([v['create_at'], str(v['target'])])
        return tuple(ret)

    @classmethod
    def faver_video_ids(cls, uid, page=None, pagesize=None, maxs=None):
        key = cls.FAVER_VIDEO_IDS % ({'uid': uid})
        if not Redis.exists(key):
            cls._load_faver_video_ids(uid)
        try:
            if page is None and pagesize is None and maxs is None:
                return Redis.zrevrange(key, 0, -1)
            if maxs:
                ids = Redis.zrevrangebyscore(key, '(%.6f' % (maxs), '-inf', start=0, num=pagesize)
            else:
                start = (page - 1) * pagesize
                stop = start + pagesize - 1
                ids = Redis.zrevrange(key, start, stop)
        except exceptions.ResponseError:
            ids = []
        return list(ids)

    @classmethod
    def faver_video_count(cls, uid):
        key = cls.FAVER_VIDEO_IDS % ({'uid': uid})
        if not Redis.exists(key):
            cls._load_faver_video_ids(uid)
        try:
            count = Redis.zcard(key)
        except exceptions.ResponseError:
            count = 0
        return count

    @classmethod
    def favor_video_uids(cls, vid):
        users = list(cls.collection.find(
            {'target': ObjectId(vid)},
            {'source': 1}
        ))
        uids = [str(user['source']) for user in users]
        return uids


class UserLikeVideo(Document):
    """用户赞的视频
    """
    collection = DB.like_video

    def create_model(self):
        _id = super(UserLikeVideo, self).create_model()
        if _id:
            video = Video.get_one(str(self.target))
            video.update_model({'$inc': {'like': 1}})
        return _id

    def delete_model(self):
        ret = super(UserLikeVideo, self).delete_model()
        if ret:
            video = Video.get_one(str(self.target))
            video.update_model({'$inc': {'like': -1}})
        return ret

    @classmethod
    def init(cls):
        doc = super(UserLikeVideo, cls).init()
        return cls(doc)

    @classmethod
    def get_by_ship(cls, sid, tid):
        ulv = cls.collection.find_one({
            'source': ObjectId(sid),
            'target': ObjectId(tid)
        })
        return cls(ulv) if ulv else None

    @classmethod
    def load_like_count(cls, vid):
        count = cls.collection.find({'target': ObjectId(vid)}).count()
        return count or 0


class GameRecommendVideo(Document):
    """游戏推荐视频
    """
    collection = DB.game_recommend_video

    RECOMMEND_VIDEO_IDS = "recommend_videos:game:%(gid)s"  # 某个游戏推荐视频队列

    def create_model(self):
        ret = super(GameRecommendVideo, self).create_model()
        if ret:
            key = self.RECOMMEND_VIDEO_IDS % ({'gid': str(self.game)})
            Redis.delete(key)
        return ret

    def update_model(self, data={}):
        ret = super(GameRecommendVideo, self).update_model(data)
        if ret:
            key = self.RECOMMEND_VIDEO_IDS % ({'gid': str(self.game)})
            Redis.delete(key)
        return ret

    def delete_model(self):
        ret = super(GameRecommendVideo, self).delete_model()
        if ret:
            key = self.RECOMMEND_VIDEO_IDS % ({'gid': str(self.game)})
            Redis.delete(key)
        return ret

    @classmethod
    @util.cached_list(lambda cls, gid: cls.RECOMMEND_VIDEO_IDS % ({'gid': gid}), snowslide=True)
    def _load_game_video_ids(cls, gid):
        videos = list(cls.collection.find(
            {'game': ObjectId(gid)},
            {'video': 1}
        ).sort("order", pymongo.ASCENDING))
        vids = [str(v['video']) for v in videos if Video.get_one(str(v['video']))]
        return vids

    @classmethod
    def game_video_ids(cls, gid):
        key = cls.RECOMMEND_VIDEO_IDS % ({'gid': gid})
        if not Redis.exists(key):
            cls._load_game_video_ids(gid)
        try:
            vids = Redis.lrange(key, 0, -1)
        except exceptions.ResponseError:
            vids = []
        return list(vids)


class ReportVideo(Document):
    collection = DB.report_video
    LATEST_REPORT_IDS = "report_videos:latest"  # 最新视频举报消息队列
    VIDEO_REPORTS = "report_video:video_id:%(vid)s"  # 视频下的所有举报消息
    REPORTED_VIDEOS = "reported_videos:latest"

    def format(self):
        time_formater = lambda x: time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(x))
        from wanx.models.user import User
        if self.get('source', 0) == 0:
            video = Video.get_one(str(self.vid), check_online=False)
            if not video:
                return None
            author = User.get_one(str(video.author), check_online=False)
            vtitle = video.title
        else:
            live = Xlive.get_live(str(self.vid))
            if not live:
                return None
            user_id = live.get('user_id', None)
            author = User.get_one(str(user_id), check_online=False)
            vtitle = live.get('name', '')
        data = {
            'video_id': self.vid,
            'video_title': vtitle,
            'video_author': author.nickname,
            'video_author_id': str(author._id),
            'type': self.type,
            'content': self.content,
            'create_at': time_formater(self.create_at),
            'count': self.collection.count({'vid': self.vid}),
            'source': 0 if self.source is None else self.source
        }

        return data

    @classmethod
    def get_reported_videos(cls, page, pagesize, maxs=None):
        key = cls.REPORTED_VIDEOS
        if not Redis.exists(key):
            cls._load_reported_videos()
        try:
            if maxs:
                ids = Redis.zrevrangebyscore(key, '(%.6f' % (maxs), '-inf', start=0,
                                             num=pagesize, withscores=True)
            else:
                start = (page - 1) * pagesize
                stop = start + pagesize - 1
                ids = Redis.zrevrange(key, start, stop)
        except exceptions.ResponseError:
            ids = []
        total = Redis.zcount(key, 0, 9e10)
        return list(ids), total

    @classmethod
    @util.cached_zset(REPORTED_VIDEOS, snowslide=True)
    def _load_reported_videos(cls):
        videos = list(cls.collection.distinct('vid'))
        ret = list()
        for v in videos:
            i = cls.collection.find({'vid': str(v)}).sort('create_at', -1)[0]
            ret.extend([i['create_at'], str(v)])
        return ret

    @classmethod
    def get_list_by_vids(cls, vids):
        time_formater = lambda x: time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(x))
        from wanx.models.user import User

        reports = list()
        for vid in vids:
            report = cls.collection.find({'vid': vid}).sort('create_at', -1)[0]
            if report.get('source', 0) == 0:
                video = Video.get_one(str(vid), check_online=False)
                if not video:
                    continue
                author = User.get_one(str(video.author), check_online=False)
                vtitle = video.title
            else:
                live = Xlive.get_live(vid)
                if not live:
                    continue
                user_id = live.get('user_id', None)
                author = User.get_one(str(user_id), check_online=False)
                vtitle = live.get('name', '')

            report = cls.collection.find({'vid': vid}).sort('create_at', -1)[0]
            report.update({
                '_id': str(report['_id']),
                'video_id': vid,
                'video_title': vtitle,
                'video_author': author.nickname,
                'video_author_id': str(author._id),
                'create_at': time_formater(report['create_at']),
                'count': cls.collection.count({'vid': vid})
            })
            reports.append(report)
        return reports

    @classmethod
    def get_reports_by_vid(cls, vid, page, pagesize):
        time_formater = lambda x: time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(x))
        reps = cls.collection.find({'vid': str(vid)}).sort('create_at', -1)
        reports = []
        start = (page - 1) * pagesize
        stop = start + pagesize
        for report in reps[start:stop]:
            report.update({
                '_id': str(report['_id']),
                'video_id': vid,
                'create_at': time_formater(report['create_at']),
            })
            reports.append(report)
        return reports, reps.count()

    @classmethod
    def get_latest_reports(cls, page, pagesize, maxs=None):
        key = cls.LATEST_REPORT_IDS
        if not Redis.exists(key):
            cls._load_latest_report_ids()
        try:
            if maxs:
                ids = Redis.zrevrangebyscore(key, '(%.6f' % (maxs), '-inf', start=0,
                                             num=pagesize, withscores=True)
            else:
                start = (page - 1) * pagesize
                stop = start + pagesize - 1
                ids = Redis.zrevrange(key, start, stop)
        except exceptions.ResponseError:
            ids = []
        return list(ids)

    @classmethod
    @util.cached_zset(LATEST_REPORT_IDS, snowslide=True)
    def _load_latest_report_ids(cls):
        reports = list(cls.collection.find().sort("create_at", pymongo.DESCENDING).limit(2000))
        ret = list()
        for i in reports:
            ret.extend([i['create_at'], str(i['_id'])])
        return tuple(ret)

    @classmethod
    def delete_reports(cls, rids):
        for rid in rids:
            cls.collection.remove({'_id': ObjectId(rid)})
        Redis.delete(cls.REPORTED_VIDEOS)

    @classmethod
    def delete_reports_by_vids(cls, vids):
        for vid in vids:
            cls.collection.remove({'vid': vid})
        Redis.delete(cls.REPORTED_VIDEOS)


class VideoCategory(Document):
    """视频分类
    _id: 分类ID
    name: 分类名称
    order: 分类排序
    create_at: 创建时间
    """
    collection = DB.video_category

    ALL_CATEGORY_IDS = 'video_category:all'  # 所有视频分类列表

    def create_model(self):
        ret = super(VideoCategory, self).create_model()
        if ret:
            Redis.delete(self.ALL_CATEGORY_IDS)
        return ret

    def update_model(self, data={}):
        ret = super(VideoCategory, self).update_model(data)
        if ret:
            Redis.delete(self.ALL_CATEGORY_IDS)
        return ret

    def delete_model(self):
        ret = super(VideoCategory, self).delete_model()
        if ret:
            Redis.delete(self.ALL_CATEGORY_IDS)
        return ret

    def format(self):
        data = {
            'category_id': str(self._id),
            'category_name': self.name,
        }
        return data

    @classmethod
    @util.cached_list(lambda cls: cls.ALL_CATEGORY_IDS, snowslide=True)
    def _load_all_category_ids(cls):
        banners = list(cls.collection.find({}, {'_id': 1}).sort("order", pymongo.ASCENDING))
        _ids = [str(b['_id']) for b in banners]
        return _ids

    @classmethod
    def all_category_ids(cls):
        key = cls.ALL_CATEGORY_IDS
        if not Redis.exists(key):
            cls._load_all_category_ids()
        try:
            _ids = Redis.lrange(key, 0, -1)
        except exceptions.ResponseError:
            _ids = []
        return list(_ids)


class CategoryVideo(Document):
    """分类下的视频
    _id: ID
    category: 分类ID
    video: 视频ID
    game:游戏ID
    create_at: 创建时间
    """
    collection = DB.category_video

    CATEGORY_GAME_VIDEO_IDS = "videos:category:%(cid)s:%(gid)s"  # 某个分类下某个游戏的视频列表

    def create_model(self):
        ret = super(CategoryVideo, self).create_model()
        if ret:
            key = self.CATEGORY_GAME_VIDEO_IDS % ({'cid': self.category, 'gid': self.game})
            try:
                if Redis.exists(key):
                    video = Video.get_one(str(self.video))
                    Redis.zadd(key, video.create_at, str(self.video))
            except exceptions.ResponseError:
                Redis.delete(key)

        return ret

    def update_model(self, data={}):
        ret = super(CategoryVideo, self).update_model(data)
        if ret:
            key = self.CATEGORY_GAME_VIDEO_IDS % ({'cid': self.category, 'gid': self.game})
            Redis.delete(key)

        return ret

    def delete_model(self):
        ret = super(CategoryVideo, self).delete_model()
        if ret:
            key = self.CATEGORY_GAME_VIDEO_IDS % ({'cid': self.category, 'gid': self.game})
            try:
                Redis.zrem(key, str(self.video))
            except exceptions.ResponseError:
                Redis.delete(key)

        return ret

    @classmethod
    def get_by_ship(cls, vid, cid):
        cg = cls.collection.find_one({
            'video': ObjectId(vid),
            'category': ObjectId(cid)
        })
        return cls(cg) if cg else None

    @classmethod
    def video_category_ids(cls, vid):
        categories = list(cls.collection.find(
            {'video': ObjectId(vid)},
            {'category': 1}
        ))
        cids = [c['category'] for c in categories if VideoCategory.get_one(str(c['category']))]
        return cids

    @classmethod
    @util.cached_zset(lambda cls, cid, gid:
                      cls.CATEGORY_GAME_VIDEO_IDS % ({'cid': cid, 'gid': gid}), snowslide=True)
    def _load_category_game_video_ids(cls, cid, gid):
        videos = list(cls.collection.find(
            {'category': ObjectId(cid), 'game': ObjectId(gid)},
            {'video': 1}
        ))
        ret = list()
        for v in videos:
            video = Video.get_one(str(v['video']))
            if video:
                ret.extend([video['create_at'], str(video._id)])

        return tuple(ret)

    @classmethod
    def category_game_video_ids(cls, cid, gid, page, pagesize, maxs=None):
        key = cls.CATEGORY_GAME_VIDEO_IDS % ({'cid': cid, 'gid': gid})
        if not Redis.exists(key):
            cls._load_category_game_video_ids(cid, gid)
        try:
            if maxs:
                vids = Redis.zrevrangebyscore(key, '(%.6f' % (maxs), '-inf', start=0, num=pagesize)
            else:
                start = (page - 1) * pagesize
                stop = start + pagesize - 1
                vids = Redis.zrevrange(key, start, stop)
        except exceptions.ResponseError:
                vids = []
        return list(vids)

    @classmethod
    def category_game_video_count(cls, cid, gid):
        key = cls.CATEGORY_GAME_VIDEO_IDS % ({'cid': cid, 'gid': gid})
        if not Redis.exists(key):
            cls._load_category_game_video_ids(cid, gid)
        try:
            count = Redis.zcard(key)
        except exceptions.ResponseError:
            count = 0

        return count


class VideoTopic(Document):
    """视频专题
    _id: 专题ID
    name: 专题名称
    order: 专题排序
    create_at: 创建时间
    """
    collection = DB.video_topic

    ALL_TOPIC_IDS = 'video_topic:all'  # 所有视频分类列表

    def create_model(self):
        ret = super(VideoTopic, self).create_model()
        if ret:
            Redis.delete(self.ALL_TOPIC_IDS)
        return ret

    def update_model(self, data={}):
        ret = super(VideoTopic, self).update_model(data)
        if ret:
            Redis.delete(self.ALL_TOPIC_IDS)
        return ret

    def delete_model(self):
        ret = super(VideoTopic, self).delete_model()
        if ret:
            Redis.delete(self.ALL_TOPIC_IDS)
        return ret

    def format(self):
        data = {
            'topic_id': str(self._id),
            'topic_name': self.name,
            'topic_image': urljoin(app.config.get("MEDIA_URL"), self.image),
            'topic_desc': self.description,
            'share_title': self.share_title,
            'share_desc': self.share_desc,
            'topic_order': self.order,
        }
        return data

    @classmethod
    @util.cached_list(lambda cls: cls.ALL_TOPIC_IDS, snowslide=True)
    def _load_all_topic_ids(cls):
        banners = list(cls.collection.find({}, {'_id': 1}).sort("order", pymongo.ASCENDING))
        _ids = [str(b['_id']) for b in banners]
        return _ids

    @classmethod
    def all_topic_ids(cls):
        key = cls.ALL_TOPIC_IDS
        if not Redis.exists(key):
            cls._load_all_topic_ids()
        try:
            _ids = Redis.lrange(key, 0, -1)
        except exceptions.ResponseError:
            _ids = []
        return list(_ids)


class TopicVideo(Document):
    """专题下的视频
    _id: ID
    topic: 专题ID
    video: 视频ID
    create_at: 创建时间
    """
    collection = DB.topic_video

    TOPIC_VIDEO_IDS = "videos:topic:%(tid)s"  # 某个专题的视频列表

    def create_model(self):
        ret = super(TopicVideo, self).create_model()
        if ret:
            key = self.TOPIC_VIDEO_IDS % ({'tid': self.topic})
            Redis.delete(key)

        return ret

    def update_model(self, data={}):
        ret = super(TopicVideo, self).update_model(data)
        if ret:
            key = self.TOPIC_VIDEO_IDS % ({'tid': self.topic})
            Redis.delete(key)

        return ret

    def delete_model(self):
        ret = super(TopicVideo, self).delete_model()
        if ret:
            key = self.TOPIC_VIDEO_IDS % ({'tid': self.topic})
            Redis.delete(key)

        return ret

    @classmethod
    def get_by_ship(cls, vid, tid):
        cg = cls.collection.find_one({
            'video': ObjectId(vid),
            'topic': ObjectId(tid)
        })
        return cls(cg) if cg else None

    @classmethod
    def video_topic_ids(cls, vid):
        topics = list(cls.collection.find(
            {'video': ObjectId(vid)},
            {'topic': 1}
        ))
        cids = [c['topic'] for c in topics if VideoTopic.get_one(str(c['topic']))]
        return cids

    @classmethod
    @util.cached_zset(lambda cls, tid:cls.TOPIC_VIDEO_IDS % ({'tid': tid}), snowslide=True)
    def _load_topic_video_ids(cls, tid):
        videos = list(cls.collection.find(
            {'topic': ObjectId(tid)},
            {'video': 1, 'create_at': 1}
        ))
        ret = list()
        for v in videos:
            video = Video.get_one(str(v['video']))
            if video:
                ret.extend([v['create_at'], str(video._id)])
        return tuple(ret)

    @classmethod
    def topic_video_ids(cls, tid, page, pagesize, maxs=None):
        key = cls.TOPIC_VIDEO_IDS % ({'tid': tid})
        if not Redis.exists(key):
            cls._load_topic_video_ids(tid)
        try:
            if maxs:
                vids = Redis.zrevrangebyscore(key, '(%.6f' % (maxs), '-inf', start=0, num=pagesize)
            else:
                start = (page - 1) * pagesize
                stop = start + pagesize - 1
                vids = Redis.zrevrange(key, start, stop)
        except exceptions.ResponseError:
                vids = []
        return list(vids)

    @classmethod
    def topic_video_count(cls, tid):
        key = cls.TOPIC_VIDEO_IDS % ({'tid': tid})
        if not Redis.exists(key):
            cls._load_topic_video_ids(tid)
        try:
            count = Redis.zcard(key)
        except exceptions.ResponseError:
            count = 0

        return count
