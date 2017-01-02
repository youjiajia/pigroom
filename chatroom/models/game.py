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
from wanx import app
from wanx.models.user import UserGroup, Group

import cPickle as cjson
import pymongo
import time


class Game(Document):
    """游戏"""

    collection = DB.games

    CACHED_OBJS = CacheDict(max_len=100, max_age_seconds=5)

    POPULAR_USER_IDS = 'game:popuser:%(date)s:%(gid)s'  # 某个游戏的达人列表

    def format(self, exclude_fields=[]):
        from wanx.models.home import Share
        share = Share.get_by_game()
        share_title = share.title if share else None
        gid = str(self._id)
        data = {
            'game_id': gid,
            'name': self.name,
            'icon': urljoin(app.config.get("MEDIA_URL"), self.icon),
            'big_icon': urljoin(app.config.get("MEDIA_URL"), self.big_icon or self.icon),
            'cover': urljoin(app.config.get("MEDIA_URL"), self.cover),
            'contain_sdk': self.contain_sdk or False,
            'url': urljoin(app.config.get("MEDIA_URL"), self.url) if self.url else None,
            'url_ios': urljoin(app.config.get("MEDIA_URL"), self.url_ios) if self.url_ios else None,
            'description': self.description,
            'intro': self.intro,
            'slogan': self.slogan,
            'developer': self.developer,
            'subscription_count': self.sub_count or 0,
            'video_count': self.video_count or 0,
            'subscribed': False,
            'tags': [],
            'create_at': self.create_at,
            'package_id': self.package_id,
            'package_version': self.version,
            'package_size': self.size,
            'package_segment': self.package_segment,
            'popular_count': 50,
            'bid': self.bid,
            'status': self.status if self.status else None,
            'is_online': self.online,
            'is_subscribe': True if self.is_subscribe else False,
            'is_download': True if self.is_download else False,
            'is_subscribe_ios': True if self.is_subscribe_ios else False,
            'is_download_ios': True if self.is_download_ios else False,
            'is_live_label': True if self.is_live_label else False,
            'share_url': urljoin(app.config.get('SHARE_URL'),
                                 '/page/html/download.html?game_id=%s' % (gid)),
            'share_title': self.share_title if self.share_title else share_title,
            'share_summary': self.summary if self.summary else self.name,
            'on_assistant': self.on_assistant is None or self.on_assistant
        }
        if 'subscribed' not in exclude_fields:
            uid = request.authed_user and str(request.authed_user._id)
            data['subscribed'] = gid in UserSubGame.sub_game_ids(uid) if uid else False
        return data

    @classmethod
    def init(cls):
        doc = super(Game, cls).init()
        doc.sub_count = 0
        doc.video_count = 0
        doc.status = const.ONLINE
        return cls(doc)

    @classmethod
    def search(cls, keyword):
        ids = cls.collection.find(
            {'name': {'$regex': keyword, '$options': 'i'}},
            {'_id': 1}
        ).sort("create_at", pymongo.DESCENDING)
        ids = [_id['_id'] for _id in ids]
        return list(ids) if ids else list()

    @classmethod
    def get_by_bid(cls, bid):
        if not bid:
            return None
        game = cls.collection.find_one({"bid": bid})
        return cls(game) if game else None

    @classmethod
    @util.cached_list(lambda cls, gid: cls.POPULAR_USER_IDS % ({'date': time.strftime("%Y%m%d"),
                                                                'gid': gid}),
                      timeout=86400, snowslide=True)
    def _load_popular_user_ids(cls, gid):
        users = DB.videos.aggregate([
            {'$match': {'game': ObjectId(gid), 'duration': {'$gte': const.DURATION},
                        'create_at': {'$gte': int(time.time()) - 7 * 24 * 60 * 60}}},
            {'$group': {'_id': '$author', 'total': {'$sum': 1}}},
            {'$sort': {'total': -1}},
            {'$limit': 50}
        ])
        uids = [str(u['_id']) for u in users]
        return uids

    @classmethod
    def popular_user_ids(cls, gid, page=None, pagesize=None):
        key = cls.POPULAR_USER_IDS % ({'date': time.strftime("%Y%m%d"), 'gid': gid})
        if not Redis.exists(key):
            cls._load_popular_user_ids(gid)
        start = (page - 1) * pagesize if page else 0
        stop = (start + pagesize - 1) if pagesize else -1
        try:
            uids = Redis.lrange(key, start, stop)
        except exceptions.ResponseError:
            uids = []
        return list(uids)

    @classmethod
    def online_games(cls):
        games = cls.collection.find({
            '$or': [{'status': {'$exists': False}},
                    {'status': const.ONLINE}]},
            {'_id': 1, 'name': 1})
        return [(g['_id'], g['name']) for g in games]

    @classmethod
    def live_games(cls):
        games = cls.collection.find(
            {'$or': [{'status': {'$exists': False}}, {'status': const.ONLINE}],
             'is_live_label': True},
            {'_id': 1, 'name': 1})
        return [(g['_id'], g['name']) for g in games]


class Category(Document):
    """游戏分类
    """
    collection = DB.category

    ALL_CATEGORY_IDS = 'category:all'  # 所有游戏分类列表

    def create_model(self):
        ret = super(Category, self).create_model()
        if ret:
            Redis.delete(self.ALL_CATEGORY_IDS)
        return ret

    def update_model(self, data={}):
        ret = super(Category, self).update_model(data)
        if ret:
            Redis.delete(self.ALL_CATEGORY_IDS)
        return ret

    def delete_model(self):
        ret = super(Category, self).delete_model()
        if ret:
            Redis.delete(self.ALL_CATEGORY_IDS)
        return ret

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


class UserSubGame(Document):
    """用户订阅的游戏
    """
    collection = DB.sub_game

    SUB_GAME_IDS = "games:usub:%(uid)s"  # 用户订阅的游戏队列

    def create_model(self):
        _id = super(UserSubGame, self).create_model()
        if _id:
            # 更新游戏订阅人数
            game = Game.get_one(str(self.target), check_online=False)
            game.update_model({'$inc': {'sub_count': 1}})

            # 更新用户订阅游戏数量
            from wanx.models.user import User
            user = User.get_one(str(self.source), check_online=False)
            user.update_model({'$inc': {'subscription_count': 1}})

            key = self.SUB_GAME_IDS % ({'uid': str(self.source)})
            try:
                if Redis.exists(key):
                    Redis.zadd(key, self.create_at, str(self.target))
            except exceptions.ResponseError:
                Redis.delete(key)

        return _id

    def delete_model(self):
        ret = super(UserSubGame, self).delete_model()
        if ret:
            # 更新游戏订阅人数
            game = Game.get_one(str(self.target), check_online=False)
            game.update_model({'$inc': {'sub_count': -1}})

            # 更新用户订阅游戏数量
            from wanx.models.user import User
            user = User.get_one(str(self.source), check_online=False)
            user.update_model({'$inc': {'subscription_count': -1}})

            key = self.SUB_GAME_IDS % ({'uid': str(self.source)})
            try:
                Redis.zrem(key, str(self.target))
            except exceptions.ResponseError:
                Redis.delete(key)

        return ret

    @classmethod
    def init(cls):
        doc = super(UserSubGame, cls).init()
        return cls(doc)

    @classmethod
    def get_by_ship(cls, uid, gid):
        usg = cls.collection.find_one({
            'source': ObjectId(uid),
            'target': ObjectId(gid)
        })
        return cls(usg) if usg else None

    @classmethod
    @util.cached_zset(lambda cls, uid: cls.SUB_GAME_IDS % ({'uid': uid}))
    def _load_sub_game_ids(cls, uid):
        games = list(cls.collection.find(
            {'source': ObjectId(uid)},
            {'target': 1, 'create_at': 1}
        ).sort("create_at", pymongo.DESCENDING))
        ret = list()
        for g in games:
            ret.extend([g['create_at'], str(g['target'])])
        return tuple(ret)

    @classmethod
    def sub_game_ids(cls, uid, page=None, pagesize=None, maxs=None):
        key = cls.SUB_GAME_IDS % ({'uid': uid})
        if not Redis.exists(key):
            cls._load_sub_game_ids(uid)
        try:
            # 不进行分页
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
    def sub_game_count(cls, uid):
        key = cls.SUB_GAME_IDS % ({'uid': uid})
        if not Redis.exists(key):
            cls._load_sub_game_ids(uid)
        try:
            count = Redis.zcard(key)
        except exceptions.ResponseError:
            count = 0
        return count


class UserPopularGame(Document):
    """用户常用游戏
    """
    collection = DB.popular_game

    POP_GAME_IDS = "games:upop:%(uid)s"  # 用户常用的游戏队列

    def create_model(self):
        _id = super(UserPopularGame, self).create_model()
        if _id:
            key = self.POP_GAME_IDS % ({'uid': str(self.source)})
            try:
                if Redis.exists(key):
                    Redis.zadd(key, self.create_at, str(self.target))
            except exceptions.ResponseError:
                Redis.delete(key)

        return _id

    def delete_model(self):
        ret = super(UserPopularGame, self).delete_model()
        if ret:
            key = self.POP_GAME_IDS % ({'uid': str(self.source)})
            try:
                Redis.zrem(key, str(self.target))
            except exceptions.ResponseError:
                Redis.delete(key)

        return ret

    @classmethod
    def init(cls):
        doc = super(UserPopularGame, cls).init()
        return cls(doc)

    @classmethod
    def get_by_ship(cls, uid, gid):
        usg = cls.collection.find_one({
            'source': ObjectId(uid),
            'target': ObjectId(gid)
        })
        return cls(usg) if usg else None

    @classmethod
    def get_game_ids(cls, uid):
        games = list(cls.collection.find(
            {'source': ObjectId(uid)},
            {'target': 1, 'create_at': 1}
        ).sort("create_at", pymongo.DESCENDING))
        ret = list()
        for g in games:
            if 'target' in g.keys():
                ret.append(str(g['target']))
        return ret

    @classmethod
    def get_user_id(cls, uid):
        user = list(cls.collection.find(
            {'source': ObjectId(uid)},
            {'create_at': 1}
        ).sort("create_at", pymongo.DESCENDING))

        return True if user else False

    @classmethod
    @util.cached_zset(lambda cls, uid: cls.POP_GAME_IDS % ({'uid': uid}))
    def _load_pop_game_ids(cls, uid):
        games = list(cls.collection.find(
            {'source': ObjectId(uid)},
            {'target': 1, 'create_at': 1}
        ).sort("create_at", pymongo.DESCENDING))
        ret = list()
        for g in games:
            ret.extend([g['create_at'], str(g['target'])])
        return tuple(ret)

    @classmethod
    def pop_game_ids(cls, uid, page=None, pagesize=None, maxs=None):
        key = cls.POP_GAME_IDS % ({'uid': uid})
        if not Redis.exists(key):
            cls._load_pop_game_ids(uid)
        try:
            # 不进行分页
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


class HotGame(Document):
    """热门游戏
    """
    collection = DB.welcome

    HOT_GAME_IDS = "games:hot"  # 全部热门游戏列表

    def create_model(self):
        ret = super(HotGame, self).create_model()
        if ret:
            Redis.delete(self.HOT_GAME_IDS)
        return ret

    def update_model(self, data={}):
        ret = super(HotGame, self).update_model(data)
        if ret:
            Redis.delete(self.HOT_GAME_IDS)
        return ret

    def delete_model(self):
        ret = super(HotGame, self).delete_model()
        if ret:
            Redis.delete(self.HOT_GAME_IDS)
        return ret

    @classmethod
    @util.cached_list(lambda cls: cls.HOT_GAME_IDS, snowslide=True)
    def _load_hot_game_ids(cls):
        games = list(cls.collection.find(
            {'available': True, 'type': 'LINK_HOT_GAME'},
            {'target': 1}
        ).sort("order", pymongo.ASCENDING))
        gids = [str(g['target']) for g in games if Game.get_one(str(g['target']))]
        return gids

    @classmethod
    def hot_game_ids(cls):
        key = cls.HOT_GAME_IDS
        if not Redis.exists(key):
            cls._load_hot_game_ids()
        try:
            gids = Redis.lrange(key, 0, -1)
        except exceptions.ResponseError:
            gids = []
        return list(gids)

    @classmethod
    def user_in_group(cls, gid, uid):
        group = Group.get_one(gid)
        # 用户组不存在直接返回True
        if group is None:
            return True
        _is_in_group = UserGroup.user_in_group(gid, uid)
        if group.gtype == const.WHITELIST_GROUP:
            return _is_in_group
        else:
            return not _is_in_group


class LiveHotGame(Document):
    """直播热门游戏
    """
    collection = DB.welcome

    HOT_GAME_IDS = "lives:games:hot"  # 全部直播热门游戏列表

    def create_model(self):
        ret = super(LiveHotGame, self).create_model()
        if ret:
            Redis.delete(self.HOT_GAME_IDS)
        return ret

    def update_model(self, data={}):
        ret = super(LiveHotGame, self).update_model(data)
        if ret:
            Redis.delete(self.HOT_GAME_IDS)
        return ret

    def delete_model(self):
        ret = super(LiveHotGame, self).delete_model()
        if ret:
            Redis.delete(self.HOT_GAME_IDS)
        return ret

    @classmethod
    @util.cached_list(lambda cls: cls.HOT_GAME_IDS, snowslide=True)
    def _load_hot_game_ids(cls):
        games = list(cls.collection.find(
            {'available': True, 'type': 'LIVE_HOT_GAME'},
            {'target': 1}
        ).sort("order", pymongo.ASCENDING))
        gids = [str(g['target']) for g in games if Game.get_one(str(g['target']))]
        return gids

    @classmethod
    def hot_game_ids(cls):
        key = cls.HOT_GAME_IDS
        if not Redis.exists(key):
            cls._load_hot_game_ids()
        try:
            gids = Redis.lrange(key, 0, -1)
        except exceptions.ResponseError:
            gids = []
        return list(gids)


class CategoryGame(Document):
    """游戏分类配置
    """
    collection = DB.category_game

    CATEGORY_GAME_IDS = "games:category:%(cid)s"  # 某个分类下的游戏列表

    def create_model(self):
        ret = super(CategoryGame, self).create_model()
        if ret:
            Redis.delete(self.CATEGORY_GAME_IDS % ({'cid': self.category}))
        return ret

    def update_model(self, data={}):
        ret = super(CategoryGame, self).update_model(data)
        if ret:
            Redis.delete(self.CATEGORY_GAME_IDS % ({'cid': self.category}))
        return ret

    def delete_model(self):
        ret = super(CategoryGame, self).delete_model()
        if ret:
            Redis.delete(self.CATEGORY_GAME_IDS % ({'cid': self.category}))
        return ret

    @classmethod
    def get_by_ship(cls, gid, cid):
        cg = cls.collection.find_one({
            'game': ObjectId(gid),
            'category': ObjectId(cid)
        })
        return cls(cg) if cg else None

    @classmethod
    def game_category_ids(cls, gid):
        categories = list(cls.collection.find(
            {'game': ObjectId(gid)},
            {'category': 1}
        ))
        cids = [c['category'] for c in categories if Category.get_one(str(c['category']))]
        return cids

    @classmethod
    @util.cached_list(lambda cls, cid: cls.CATEGORY_GAME_IDS % ({'cid': cid}), snowslide=True)
    def _load_category_game_ids(cls, cid):
        games = list(cls.collection.find(
            {'category': ObjectId(cid)},
            {'game': 1}
        ).sort("order", pymongo.ASCENDING))
        gids = [str(g['game']) for g in games if Game.get_one(str(g['game']))]
        return gids

    @classmethod
    def category_game_ids(cls, cid):
        key = cls.CATEGORY_GAME_IDS % ({'cid': cid})
        if not Redis.exists(key):
            cls._load_category_game_ids(cid)
        try:
            gids = Redis.lrange(key, 0, -1)
        except exceptions.ResponseError:
            gids = []
        return list(gids)


class GameRecommendSubscribe(Document):
    """推荐游戏订阅
    """
    collection = DB.game_recommend_subscribe

    GAME_RECOMMEND_SUBSCRIBE = "games:recommend:subscribe"  # 全部推荐游戏列表

    def create_model(self):
        ret = super(GameRecommendSubscribe, self).create_model()
        if ret:
            Redis.delete(self.GAME_RECOMMEND_SUBSCRIBE)
        return ret

    def update_model(self, data={}):
        ret = super(GameRecommendSubscribe, self).update_model(data)
        if ret:
            Redis.delete(self.GAME_RECOMMEND_SUBSCRIBE)
        return ret

    def delete_model(self):
        ret = super(GameRecommendSubscribe, self).delete_model()
        if ret:
            Redis.delete(self.GAME_RECOMMEND_SUBSCRIBE)
        return ret

    @classmethod
    @util.cached_list(lambda cls: cls.GAME_RECOMMEND_SUBSCRIBE, snowslide=True)
    def _load_recommend_sub_ids(cls):
        games = list(cls.collection.find().sort("order", pymongo.ASCENDING).limit(12))
        gids = [str(g['game']) for g in games if Game.get_one(str(g['game']))]
        return gids

    @classmethod
    def recommend_sub_ids(cls):
        key = cls.GAME_RECOMMEND_SUBSCRIBE
        if not Redis.exists(key):
            cls._load_recommend_sub_ids()
        try:
            gids = Redis.lrange(key, 0, -1)
        except exceptions.ResponseError:
            gids = []
        return list(gids)


class GameActivity(Document):
    """推广活动页游戏推荐
    """
    collection = DB.game_activity

    GAME_ACTIVITY = "games:activity:%(activity_id)s"

    def create_model(self):
        ret = super(GameActivity, self).create_model()
        if ret:
            key = self.GAME_ACTIVITY % ({'activity_id': self.activity})
            Redis.delete(key)
        return ret

    def update_model(self, data={}):
        ret = super(GameActivity, self).update_model(data)
        if ret:
            key = self.GAME_ACTIVITY % ({'activity_id': self.activity})
            Redis.delete(key)
        return ret

    def delete_model(self):
        ret = super(GameActivity, self).delete_model()
        if ret:
            key = self.GAME_ACTIVITY % ({'activity_id': self.activity})
            Redis.delete(key)
        return ret

    def format(self):
        data = {
            'name': self.game_name,
            'icon': urljoin(app.config.get("MEDIA_URL"), self.game_icon),
            'game_id': self.game,
            'is_download': self.is_download,
            'package_id': self.package_id
        }
        return data

    @classmethod
    def _load_game_activity_ids(cls, aid, key):
        games = list(cls.collection.find({'activity': ObjectId(aid)}))
        game_activity_ids = list()
        for g in games:
            game_activity_ids.append(str(g['game']))
        return Redis.setex(key, 86400, cjson.dumps(game_activity_ids, 2))

    @classmethod
    def game_activity_ids(cls, aid):
        key = cls.GAME_ACTIVITY % ({'activity_id': aid})
        if not Redis.exists(key):
            cls._load_game_activity_ids(aid, key)
        try:
            game_activity = Redis.get(key)
        except exceptions.ResponseError:
            game_activity = []

        return cjson.loads(game_activity)

    @classmethod
    def get_by_aid(cls, aid):
        games = cls.collection.find({'activity': ObjectId(aid)})
        return [cls(game) for game in games]


class GameDownload(Document):
    """游戏下载记录
    """
    collection = DB.game_download


class WebGame(Document):
    """游戏"""

    collection = DB.web_games

    CACHED_OBJS = CacheDict(max_len=100, max_age_seconds=5)

    def format(self, exclude_fields=[]):
        gid = str(self._id)
        data = {
            'game_id': gid,
            'migu_code': self.migu_code,
            'name': self.name,
            'url': urljoin(app.config.get("MEDIA_URL"), self.url) if self.url else None,
            'description': self.description,
            'categories': self.categories,
            'engine': self.engine,
            'intro': self.intro,
            'slogan': self.slogan,
            'developer': self.developer,
            'cover': urljoin(app.config.get("MEDIA_URL"), self.cover),
            'icon': urljoin(app.config.get("MEDIA_URL"), self.icon),
            'big_icon': urljoin(app.config.get("MEDIA_URL"), self.big_icon or self.icon),
            'create_at': self.create_at,
            'order': self.order,
            'orientation': self.orientation or 0,
        }
        return data

    @classmethod
    def online_games(cls):
        games = cls.collection.find({
            '$or': [{'status': {'$exists': False}},
                    {'status': const.ONLINE}]},
            {'_id': 1, 'name': 1})
        return [(g['_id'], g['name']) for g in games]


class GameGrid(Document):
    """游戏宫格"""
    collection = DB.game_grids
    ALL_IDS = 'game:grids:all'  # 所有游戏页宫格列表

    def format(self):
        data = {
            'id': str(self._id),
            'name': self.name,
            'icon': urljoin(app.config.get("MEDIA_URL"), self.icon),
            'action': self.action,
            'order': self.order
        }
        return data

    @classmethod
    @util.cached_list(lambda cls: cls.ALL_IDS, snowslide=True)
    def _load_all_ids(cls):
        objs = list(cls.collection.find(
            {},
            {'_id': 1}
        ).sort("order", pymongo.ASCENDING))
        _ids = [str(i['_id']) for i in objs]
        return _ids

    @classmethod
    def all_ids(cls):
        key = cls.ALL_IDS
        if not Redis.exists(key):
            cls._load_all_ids()
        try:
            bids = Redis.lrange(key, 0, -1)
        except exceptions.ResponseError:
            bids = []
        return list(bids)

    @classmethod
    def all_grids(cls):
        grids = cls.collection.find({}).sort("order", pymongo.ASCENDING)
        return [cls(g).format() for g in grids]

    @classmethod
    def platform_grids(cls, os):
        if os == 'android':
            oss = [os, None]
        else:
            oss = [os]
        ids = cls.all_ids()
        return [cls(g).format() for g in cls.get_list(ids) if g.os in oss]


class GameAds(Document):
    """游戏页广告"""
    collection = DB.game_ads
    CACHED_OBJS = CacheDict(max_len=100, max_age_seconds=5)
    ALL_AD_IDS = 'game_ads:all'  # 所有游戏页广告列表

    def format(self):
        data = {
            'banner_id': str(self._id),
            'image': urljoin(app.config.get("MEDIA_URL"), self.image),
            'action': self.action,
            'duration': self.duration,
            'order': self.order,
            'expire_at': self.expire_at
        }
        return data

    @property
    def online(self):
        ts = time.time()
        # 还未到上线时间
        if self.begin_at and self.begin_at > ts:
            return False

        # 已到下线时间
        if self.expire_at and self.expire_at < ts:
            return False

        return True

    @classmethod
    @util.cached_list(lambda cls: cls.ALL_AD_IDS, snowslide=True)
    def _load_all_ad_ids(cls):
        ads = list(cls.collection.find(
            {'expire_at': {'$gte': time.time()}},
            {'_id': 1}
        ).sort("order", pymongo.ASCENDING))
        adids = [str(b['_id']) for b in ads]
        return adids

    @classmethod
    def all_ad_ids(cls):
        key = cls.ALL_AD_IDS
        if not Redis.exists(key):
            cls._load_all_ad_ids()
        try:
            bids = Redis.lrange(key, 0, -1)
        except exceptions.ResponseError:
            bids = []
        return list(bids)

    @classmethod
    def user_in_group(cls, gid, uid):
        group = Group.get_one(gid)
        # 用户组不存在直接返回True
        if group is None:
            return True
        _is_in_group = UserGroup.user_in_group(gid, uid)
        if group.gtype == const.WHITELIST_GROUP:
            return _is_in_group
        else:
            return not _is_in_group


class GameTopic(Document):
    """游戏页专题"""
    collection = DB.game_topics
    CACHED_OBJS = CacheDict(max_len=100, max_age_seconds=5)
    ALL_IDS = 'game_topics:all'  # 所有游戏专题列表

    def format(self):
        data = {
            'id': str(self._id),
            'name': self.name,
            'description': self.description,
            'big_icon': urljoin(app.config.get("MEDIA_URL"), self.big_icon),
            'icon': urljoin(app.config.get("MEDIA_URL"), self.icon),
            'icon_type': self.use_icon,
            'action': self.action,
            'order': self.order,
            'release_day': self.release_at,
            'visitor_count': self.visitor_count,
            'expire_at': self.expire_at
        }
        return data

    @property
    def online(self):
        ts = time.time()
        # 还未到上线时间
        if self.begin_at and self.begin_at > ts:
            return False

        # 已到下线时间
        if self.expire_at and self.expire_at < ts:
            return False

        return True

    @classmethod
    @util.cached_list(lambda cls: cls.ALL_IDS, snowslide=True)
    def _load_all_ids(cls):
        all_ids = list(cls.collection.find(
            {'expire_at': {'$gte': time.time()}},
            {'_id': 1}
        ).sort("order", pymongo.ASCENDING))
        ids = [str(r['_id']) for r in all_ids]
        return ids

    @classmethod
    def all_ids(cls):
        key = cls.ALL_IDS
        if not Redis.exists(key):
            cls._load_all_ids()
        try:
            ids = Redis.lrange(key, 0, -1)
        except exceptions.ResponseError:
            ids = []
        return list(ids)

    @classmethod
    def user_in_group(cls, gid, uid):
        group = Group.get_one(gid)
        # 用户组不存在直接返回True
        if group is None:
            return True
        _is_in_group = UserGroup.user_in_group(gid, uid)
        if group.gtype == const.WHITELIST_GROUP:
            return _is_in_group
        else:
            return not _is_in_group


class TopicGame(Document):
    collection = DB.topic_games
    TOPIC_GAME_IDS = "games:topic:%(tid)s"  # 某个专题的游戏列表

    @classmethod
    def topic_game_ids(cls, tid, page, pagesize, maxs):
        if maxs:
            res = cls.collection.find({'topic': ObjectId(tid), 'order': {'$gt': int(maxs)}},
                                      {'_id': 1, 'game': 1}
                                      ).sort('order', pymongo.ASCENDING).limit(pagesize)
        else:
            start = max(0, (page - 1) * pagesize)
            stop = start + pagesize - 1
            res = cls.collection.find({'topic': ObjectId(tid)},
                                      {'_id': 1, 'game': 1}
                                      ).sort('order', pymongo.ASCENDING).skip(start).limit(pagesize)
        return [[str(tg['_id']), str(tg['game'])] for tg in res]


class WebGameAds(Document):
    """页游广告"""
    collection = DB.webgame_ads
    CACHED_OBJS = CacheDict(max_len=100, max_age_seconds=5)
    ALL_IDS = 'webgame_ads:all'  # 所有页游广告列表

    def format(self):
        data = {
            'banner_id': str(self._id),
            'image': urljoin(app.config.get("MEDIA_URL"), self.image),
            'action': self.action,
            'duration': self.duration,
            'order': self.order,
            'expire_at': self.expire_at
        }
        return data

    @property
    def online(self):
        ts = time.time()
        # 还未到上线时间
        if self.begin_at and self.begin_at > ts:
            return False

        # 已到下线时间
        if self.expire_at and self.expire_at < ts:
            return False

        return True

    @classmethod
    @util.cached_list(lambda cls: cls.ALL_IDS, snowslide=True)
    def _load_all_ad_ids(cls):
        ads = list(cls.collection.find(
            {'expire_at': {'$gte': time.time()}},
            {'_id': 1}
        ).sort("order", pymongo.ASCENDING))
        adids = [str(b['_id']) for b in ads]
        return adids

    @classmethod
    def all_ad_ids(cls):
        key = cls.ALL_IDS
        if not Redis.exists(key):
            cls._load_all_ad_ids()
        try:
            bids = Redis.lrange(key, 0, -1)
        except exceptions.ResponseError:
            bids = []
        return list(bids)

    @classmethod
    def user_in_group(cls, gid, uid):
        group = Group.get_one(gid)
        # 用户组不存在直接返回True
        if group is None:
            return True
        _is_in_group = UserGroup.user_in_group(gid, uid)
        if group.gtype == const.WHITELIST_GROUP:
            return _is_in_group
        else:
            return not _is_in_group


class GameMainstay(Document):
    """主推游戏"""
    collection = DB.game_mainstay
    CACHED_OBJS = CacheDict(max_len=100, max_age_seconds=5)
    ALL_IDS = 'game_mainstays:all'  # 所有主推游戏列表

    def format(self):
        game = Game.get_one(self.game)
        data = {
            'id': str(self._id),
            'name': self.name,
            'order': self.order,
            'image': urljoin(app.config.get("MEDIA_URL"), self.image),
            'game': game.format(),
        }
        return data

    @property
    def online(self):
        return True

    @classmethod
    @util.cached_list(lambda cls: cls.ALL_IDS, snowslide=True)
    def _load_all_ids(cls):
        ads = list(cls.collection.find(
            {},
            {'_id': 1}
        ).sort("order", pymongo.ASCENDING))
        adids = [str(b['_id']) for b in ads]
        return adids

    @classmethod
    def all_ids(cls):
        key = cls.ALL_IDS
        if not Redis.exists(key):
            cls._load_all_ids()
        try:
            bids = Redis.lrange(key, 0, -1)
        except exceptions.ResponseError:
            bids = []
        return list(bids)

    @classmethod
    def user_in_group(cls, gid, uid):
        group = Group.get_one(gid)
        # 用户组不存在直接返回True
        if group is None:
            return True
        _is_in_group = UserGroup.user_in_group(gid, uid)
        if group.gtype == const.WHITELIST_GROUP:
            return _is_in_group
        else:
            return not _is_in_group


class GameModule(Document):
    """游戏模块"""
    collection = DB.game_module
    ALL_IDS = 'games:modules:%(os)s'

    def format(self):
        gids = ModuleGame.module_game_ids(str(self._id))
        games = [g.format() for g in Game.get_list(gids)]
        data = {
            'id': self._id,
            'order': self.order,
            'name': self.name,
            'icon': urljoin(app.config.get("MEDIA_URL"), self.icon),
            'games': games
        }
        return data

    @classmethod
    def _load_os_module_ids(cls, os, key):
        modules = list(cls.collection.find({'os': os}).sort("order", pymongo.ASCENDING))
        _ids = list()
        for m in modules:
            _ids.append(str(m['_id']))
        return Redis.setex(key, 86400, cjson.dumps(_ids, 2))

    @classmethod
    def all_ids_by_os(cls, os):
        key = cls.ALL_IDS % ({'os': os})
        if not Redis.exists(key):
            cls._load_os_module_ids(os, key)
        try:
            _ids = Redis.get(key)
        except exceptions.ResponseError:
            _ids = []
        return cjson.loads(_ids)

    @classmethod
    def all_modules_by_os(cls, os):
        objs = list(cls.collection.find({'os': os}).sort("order", pymongo.ASCENDING))
        return [cls(i).format() for i in objs]

    @classmethod
    def user_in_group(cls, gid, uid):
        group = Group.get_one(gid)
        # 用户组不存在直接返回True
        if group is None:
            return True
        _is_in_group = UserGroup.user_in_group(gid, uid)
        if group.gtype == const.WHITELIST_GROUP:
            return _is_in_group
        else:
            return not _is_in_group


class ModuleGame(Document):
    """模块游戏"""
    collection = DB.module_game
    ALL_IDS = 'games:module:%(mid)s'    # 某个模块下的游戏列表

    @classmethod
    @util.cached_list(lambda cls, mid: cls.ALL_IDS % ({'mid': mid}), snowslide=True)
    def _load_module_game_ids(cls, mid):
        games = list(cls.collection.find(
            {'module': ObjectId(mid)},
            {'game': 1}
        ).sort("order", pymongo.ASCENDING))
        gids = [str(g['game']) for g in games if Game.get_one(str(g['game']))]
        return gids

    @classmethod
    def module_game_ids(cls, mid):
        key = cls.ALL_IDS % ({'mid': mid})
        if not Redis.exists(key):
            cls._load_module_game_ids(mid)
        try:
            gids = Redis.lrange(key, 0, -1)
        except exceptions.ResponseError:
            gids = []
        return list(gids)


class HotRecommendGame(Document):
    """热门推荐游戏
    """
    collection = DB.hot_games

    HOT_GAME_IDS = "games:hot_games"  # 全部热门游戏列表

    def create_model(self):
        ret = super(HotRecommendGame, self).create_model()
        if ret:
            Redis.delete(self.HOT_GAME_IDS)
        return ret

    def update_model(self, data={}):
        ret = super(HotRecommendGame, self).update_model(data)
        if ret:
            Redis.delete(self.HOT_GAME_IDS)
        return ret

    def delete_model(self):
        ret = super(HotRecommendGame, self).delete_model()
        if ret:
            Redis.delete(self.HOT_GAME_IDS)
        return ret

    @classmethod
    @util.cached_list(lambda cls: cls.HOT_GAME_IDS, snowslide=True)
    def _load_hot_game_ids(cls):
        games = list(cls.collection.find({}).sort("order", pymongo.ASCENDING))
        gids = [str(g['game']) for g in games if Game.get_one(str(g['game']))]
        return gids

    @classmethod
    def hot_game_ids(cls):
        key = cls.HOT_GAME_IDS
        if not Redis.exists(key):
            cls._load_hot_game_ids()
        try:
            gids = Redis.lrange(key, 0, -1)
        except exceptions.ResponseError:
            gids = []
        return list(gids)

    @classmethod
    def clear_redis(cls):
        Redis.delete(cls.HOT_GAME_IDS)

    @classmethod
    def check_unique(cls, game, order, _id=None):
        res = cls.collection.find_one({'game': game, '_id': {'$ne': _id}})
        if res:
            return 1
        res = cls.collection.find_one({'order': order, '_id': {'$ne': _id}})
        if res:
            return 2
        return 0
