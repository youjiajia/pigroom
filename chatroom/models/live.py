# -*- coding: utf8 -*-
import time
from urlparse import urljoin

from bson.objectid import ObjectId
from redis import exceptions

from wanx import app
from wanx.models import Document
from wanx.models.gift import UserGiftLog
from wanx.models.user import User
from wanx.base import util, const
from wanx.base.xmongo import DB
from wanx.base.xredis import Redis

import pymongo
import cPickle as cjson

from wanx.models.user import UserGroup, Group


class Live_Activity(Document):
    """直播活动
    """
    collection = DB.live_activity

    LIVE_HOT_USER = "live:hot:user:%(aid)s"
    LIVE_NEW_USER = "live:new:user:%(aid)s"

    def create_model(self):
        _id = super(Live_Activity, self).create_model()
        if _id:
            key = self.LIVE_HOT_USER % ({'aid': str(self.activity_id)})
            Redis.delete(key)
            key = self.LIVE_NEW_USER % ({'aid': str(self.activity_id)})
            Redis.delete(key)
        return _id

    def update_model(self, data={}):
        obj = super(Live_Activity, self).update_model(data)
        if obj:
            key = self.LIVE_HOT_USER % ({'aid': str(self.activity_id)})
            Redis.delete(key)
            key = self.LIVE_NEW_USER % ({'aid': str(self.activity_id)})
            Redis.delete(key)
        return obj

    def delete_model(self):
        ret = super(Live_Activity, self).delete_model()
        if ret:
            key = self.LIVE_HOT_USER % ({'aid': str(self.activity_id)})
            Redis.delete(key)
            key = self.LIVE_NEW_USER % ({'aid': str(self.activity_id)})
            Redis.delete(key)
        return ret

    @classmethod
    def get_live_user_top(cls, aid, member, begin_at, end_at):
        key = cls.LIVE_HOT_USER % ({'aid': aid})
        if not Redis.exists(key):
            cls._load_get_live_hot_users(aid, begin_at, end_at)
        try:
            top = Redis.zrevrank(key, member)
        except exceptions.ResponseError:
            return None
        if not isinstance(top, int):
            return None
        return top + 1

    @classmethod
    def get_activity_live(cls, uid, aid):
        activity_live = list(cls.collection.find(
            {'author': ObjectId(uid), 'activity_id': ObjectId(aid)}
        ))
        return activity_live

    @classmethod
    @util.cached_zset(lambda cls, aid, begin_at, end_at: cls.LIVE_HOT_USER % ({'aid': aid}), snowslide=True)
    def _load_get_live_hot_users(cls, aid, begin_at, end_at):
        users = list(cls.collection.find({'activity_id': ObjectId(aid)}))
        ret = list()
        for user in users:
            uid = str(user['author'])
            score = util.hot_live_user_score(UserGiftLog.get_user_total_gold(uid, begin_at, end_at),
                                             int(user['create_at']))
            ret.extend([score, uid])
        return tuple(ret)

    @classmethod
    def get_live_hot_user(cls, aid, pagesize, begin_at, end_at, maxs=None):
        key = cls.LIVE_HOT_USER % ({'aid': aid})
        Redis.delete(key)
        cls._load_get_live_hot_users(aid, begin_at, end_at)
        try:
            user_scores = Redis.zrevrangebyscore(key, '(%.6f' % (maxs), '-inf', start=0, num=pagesize, withscores=True)
            user_scores = [(us[0], us[1], cls.get_live_user_top(aid, us[0], begin_at, end_at)) for us in user_scores]
        except exceptions.ResponseError:
            user_scores = []

        return user_scores

    @classmethod
    @util.cached_zset(lambda cls, aid: cls.LIVE_NEW_USER % ({'aid': aid}), snowslide=True)
    def _load_get_live_new_users(cls, aid):
        users = list(cls.collection.find(
            {'activity_id': ObjectId(aid)}
        ).sort("create_at", pymongo.DESCENDING))
        ret = list()
        for user in users:
            ret.extend([user['create_at'], str(user['author'])])
        return tuple(ret)

    @classmethod
    def get_live_new_user(cls, aid, pagesize, maxs=None):
        key = cls.LIVE_NEW_USER % ({'aid': aid})
        if not Redis.exists(key):
            cls._load_get_live_new_users(aid)
        try:
            users = Redis.zrevrangebyscore(key, '(%.6f' % (maxs), '-inf', start=0, num=pagesize)
        except exceptions.ResponseError:
            users = []

        return users

    @classmethod
    def get_activity_live_by_authors(cls, aid, authors):
        activity_lives = list(cls.collection.find(
            {
                'activity_id': ObjectId(aid),
                'author': {'$in': authors}
            }
        ))
        return [str(a['author']) for a in activity_lives]


class WatchLiveTask(Document):
    collection = DB.watch_live_task

    LIVE_USER_TASK = 'live:task:%(date)s:%(uid)s'
    LIVE_TASKS = 'live:tasks'

    def format(self, uid):
        tid = str(self._id)
        datestr = time.strftime('%y%m%d', time.localtime())
        if uid:
            key = self.LIVE_USER_TASK % {'uid': uid, 'date': datestr}
            left_chance = int(Redis.hget(key, tid))
        else:
            left_chance = self.chance
        icon_login = self.icon_login or self.icon
        icon_break = self.icon_break or self.icon
        icon_reward = self.icon_reward or self.icon
        icon_out = self.icon_out or self.icon
        data = {
            'id': tid,
            'name': self.name,
            'duration': self.duration,
            'expire_at': self.expire_at,
            'chance': left_chance,
            'icon': urljoin(app.config.get("MEDIA_URL"), self.icon),
            'icon_login': urljoin(app.config.get("MEDIA_URL"), icon_login),
            'icon_break': urljoin(app.config.get("MEDIA_URL"), icon_break),
            'icon_reward': urljoin(app.config.get("MEDIA_URL"), icon_reward),
            'icon_out': urljoin(app.config.get("MEDIA_URL"), icon_out),
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
    @util.cached_hash(lambda cls, uid, datestr: cls.LIVE_USER_TASK % ({'uid': uid, 'date': datestr}), snowslide=True)
    def _load_user_tasks(cls, uid, datestr):
        tasks = cls.collection.find({'expire_at': {'$gt': time.time()}}, {'_id': 1, 'chance': 1})
        utasks = {}
        for task in tasks:
            utasks[task['_id']] = task['chance']
        return utasks

    @classmethod
    def get_user_tids(cls, uid):
        datestr = time.strftime('%y%m%d', time.localtime())
        key = cls.LIVE_USER_TASK % {'uid': uid, 'date': datestr}
        if not Redis.exists(key):
            cls._load_user_tasks(uid, datestr)
        try:
            tids = Redis.hgetall(key)
        except exceptions.ResponseError:
            tids = []
        return tids

    @classmethod
    @util.cached_list(lambda cls: cls.LIVE_TASKS, snowslide=True)
    def _load_live_tasks(cls):
        all_ids = list(cls.collection.find(
            {'expire_at': {'$gte': time.time()}},
            {'_id': 1}
        ))
        ids = [str(r['_id']) for r in all_ids]
        return ids

    @classmethod
    def get_live_tids(cls):
        key = cls.LIVE_TASKS
        if not Redis.exists(key):
            cls._load_live_tasks()
        try:
            ids = Redis.lrange(key, 0, -1)
        except exceptions.ResponseError:
            ids = []
        return list(ids)

    @classmethod
    def query_left_chance(cls, uid, tid):
        datestr = time.strftime('%y%m%d', time.localtime())
        key = cls.LIVE_USER_TASK % {'uid': uid, 'date': datestr}
        left_chance = Redis.hget(key, tid)
        if left_chance is None:
            left_chance = 0
        return int(left_chance)

    @classmethod
    def update_left_chance(cls, uid, tid):
        datestr = time.strftime('%y%m%d', time.localtime())
        key = cls.LIVE_USER_TASK % {'uid': uid, 'date': datestr}
        left_chance = Redis.hget(key, tid)
        if left_chance is None:
            left_chance = cls.get_one(tid)['chance']
        if int(left_chance) < 1:
            return False
        left_chance = int(left_chance) - 1
        Redis.hset(key, tid, left_chance)
        return True

    @classmethod
    def clear_redis(cls):
        Redis.delete(cls.LIVE_TASKS)

    @classmethod
    def all_tasks_for_admin(cls):
        items = cls.collection.find({}, {'_id': 1, 'name': 1})
        return [(i['_id'], i['name']) for i in items]

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


class WatchLiveTaskItem(Document):
    collection = DB.watch_live_task_item

    WLT_ITEM_KEY = 'wlt_item:%(wlt_id)s'

    def format(self):
        data = {
            'id': self._id,
            'wlt_id': self.wlt_id,
            'product_id': self.product_id,
            'product_num': self.product_num,
            'title': self.title,
            'identity': self.identity,
            'description': self.description or '',
        }
        return data

    @classmethod
    def get_task_items(cls, wlt_id):
        key = cls.WLT_ITEM_KEY % ({'wlt_id': wlt_id})
        items = Redis.get(key)
        if items:
            items = cjson.loads(items)
        else:
            items = list(cls.collection.find({'wlt_id': ObjectId(wlt_id)}))
            Redis.setex(key, 86400, cjson.dumps(items, 2))
        return [cls(i) for i in items]

    @classmethod
    def get_item_by_identity(cls, wlt_id, identity):
        if not identity:
            return None

        items = filter(lambda x: x['wlt_id'] == ObjectId(wlt_id) and x['identity'] == identity,
                       cls.get_task_items(wlt_id))
        return items[0] if items else None

    @classmethod
    def clear_redis(cls, wlt_id):
        key = cls.WLT_ITEM_KEY % ({'wlt_id': wlt_id})
        Redis.delete(key)

    def update_left(self):
        used = self.use_num or 0
        left = self.left_num or 0
        used += 1
        left -= 1
        self.update_model({'$set': {'use_num': used, 'left_num': left}})


class LiveRedPacket(Document):
    collection = DB.live_red_packet
    ALL_IDS = 'live:redpacket:all'

    def format(self, total=1):
        data = {
            'id': str(self._id),
            'expire_at': self.expire_at,
            'icon_login': urljoin(app.config.get("MEDIA_URL"), self.icon_login),
            'icon_open': urljoin(app.config.get("MEDIA_URL"), self.icon_open),
            'icon_error': urljoin(app.config.get("MEDIA_URL"), self.icon_error),
            'icon_done': urljoin(app.config.get("MEDIA_URL"), self.icon_done),
            'icon_button': urljoin(app.config.get("MEDIA_URL"), self.icon_button),
            'icon_button_open': urljoin(app.config.get("MEDIA_URL"), self.icon_button_open),
            'chance': self.chance,
            'item_count': self.item_count or 0,
            'share_action': None,
            'share_title': self.share_title,
            'share_description': self.share_description,
            'share_icon': None,
            'total': total,
        }
        return data

    @classmethod
    @util.cached_list(lambda cls: cls.ALL_IDS, snowslide=True)
    def _load_live_redpackets(cls):
        all_ids = list(cls.collection.find(
            {'expire_at': {'$gte': time.time()}},
            {'_id': 1}
        ))
        ids = [str(r['_id']) for r in all_ids]
        return ids

    @classmethod
    def all_ids(cls):
        key = cls.ALL_IDS
        if not Redis.exists(key):
            cls._load_live_redpackets()
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

    @property
    def online(self):
        _is_online = super(LiveRedPacket, self).online
        if not _is_online:
            return False

        ts = time.time()
        # 还未到上线时间
        if self.begin_at and self.begin_at > ts:
            return False

        # 已到下线时间
        if self.expire_at and self.expire_at < ts:
            return False

        return True

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


class UserRedPacket(Document):
    collection = DB.user_red_packet
    USER_REDPACKET_IDS = 'live:redpacket:user:%(uid)s'

    def format(self, total, no_share=False):
        owner = User.get_one(self.user_id)
        if not owner:
            return None
        activity = LiveRedPacket.get_one(self.active_id, check_online=False)
        if not activity:
            return None
        source_id = str(self._id)
        if self.source == 3:
            # 不可分享的红包分享操作返回null
            share_action = None
        else:
            share_action = activity.share_action
            cnt = '&' if share_action.count('?') else '?'
            _source_id = None if no_share else source_id
            share_action = '%s%ssource_id=%s&user_id=%s' % (share_action, cnt, _source_id, str(self.user_id))
        share_icon = None
        if activity.share_icon:
            share_icon = urljoin(app.config.get("MEDIA_URL"), activity.share_icon)
        data = {
            'id': source_id,
            'expire_at': self.expire_at,
            'icon_login': urljoin(app.config.get("MEDIA_URL"), activity.icon_login),
            'icon_open': urljoin(app.config.get("MEDIA_URL"), activity.icon_open),
            'icon_error': urljoin(app.config.get("MEDIA_URL"), activity.icon_error),
            'icon_done': urljoin(app.config.get("MEDIA_URL"), activity.icon_done),
            'icon_button': urljoin(app.config.get("MEDIA_URL"), activity.icon_button),
            'icon_button_open': urljoin(app.config.get("MEDIA_URL"), activity.icon_button_open),
            'chance': self.chance,
            'item_count': self.item_count or 0,
            'share_action': share_action,
            'share_title': activity.share_title,
            'share_description': activity.share_description,
            'share_icon': share_icon,
            'total': total,
            'owner': owner.format(),
        }
        return data

    def query_left_chance(self):
        return self.chance

    @classmethod
    @util.cached_list(lambda cls, uid: cls.USER_REDPACKET_IDS % ({'uid': uid}), snowslide=True)
    def _load_user_redpackets(cls, uid):
        all_ids = list(cls.collection.find(
            {'user_id': uid, 'expire_at': {'$gte': time.time()}},
            {'_id': 1}
        ))
        ids = [str(r['_id']) for r in all_ids]
        return ids

    @classmethod
    def user_red_packets(cls, uid):
        key = cls.USER_REDPACKET_IDS % ({'uid': uid})
        if not Redis.exists(key):
            cls._load_user_redpackets(uid)
        try:
            ids = Redis.lrange(key, 0, -1)
        except exceptions.ResponseError:
            ids = []
        return list(ids)

    def create_model(self):
        ret = super(UserRedPacket, self).create_model()
        key = self.USER_REDPACKET_IDS % ({'uid': self.user_id})
        Redis.delete(key)
        return ret

    @property
    def online(self):
        _is_online = super(UserRedPacket, self).online
        if not _is_online:
            return False

        ts = time.time()
        # 还未到上线时间
        if self.begin_at and self.begin_at > ts:
            return False

        # 已到下线时间
        if self.expire_at and self.expire_at < ts:
            return False

        return True

    def take_chance(self):
        data = {
            '$set': {'chance': self.chance-1}
        }
        ret = self.update_model(data)
        return ret

    def take_item(self):
        data = {
            '$set': {'item_count': self.item_count-1}
        }
        ret = self.update_model(data)
        return ret

    @classmethod
    def check_live_redpacket(cls, uid, active_id):
        _ids = cls.user_red_packets(uid)
        for rp in cls.get_list(_ids):
            if rp.active_id == active_id and rp.source == 0:
                return True
        return False

    @classmethod
    def check_shared_redpacket(cls, uid, campaign_id, resource_id):
        _ids = cls.user_red_packets(uid)
        for rp in cls.get_list(_ids):
            if rp.campaign_id == campaign_id and rp.resource_id == resource_id and rp.source == 1:
                return True
        return False


class LiveRedPacketItem(Document):
    collection = DB.live_red_packet_items
    LRP_ITEM_KEY = 'lrp_item:%(lrp_id)s'

    def format(self):
        data = {
            'id': self._id,
            'lrp_id': self.lrp_id,
            'product_id': self.product_id,
            'product_num': self.product_num,
            'title': self.title,
            'identity': self.identity,
            'description': self.description or '',
        }
        return data

    @classmethod
    def get_redpacket_items(cls, lrp_id):
        key = cls.LRP_ITEM_KEY % ({'lrp_id': lrp_id})
        items = Redis.get(key)
        if items:
            items = cjson.loads(items)
        else:
            items = list(cls.collection.find({'lrp_id': ObjectId(lrp_id)}))
            Redis.setex(key, 86400, cjson.dumps(items, 2))
        return [cls(i) for i in items]

    @classmethod
    def get_item_by_identity(cls, lrp_id, identity):
        if not identity:
            return None

        items = filter(lambda x: x['lrp_id'] == ObjectId(lrp_id) and x['identity'] == identity,
                       cls.get_redpacket_items(lrp_id))
        return items[0] if items else None

    def update_left(self):
        used = self.use_num or 0
        left = self.left_num or 0
        used += 1
        left -= 1
        self.update_model({'$set': {'use_num': used, 'left_num': left}})
