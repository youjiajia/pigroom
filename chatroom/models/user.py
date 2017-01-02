# -*- coding: utf8 -*-
from bson.binary import Binary
from bson.objectid import ObjectId
from flask import request
from redis import exceptions
from urlparse import urljoin
from wanx.base.spam import Spam
from wanx.base.xredis import Redis, MRedis
from wanx.base.xmongo import DB
from wanx.models import Document
from wanx.base import util, const, error
from wanx.base.cachedict import CacheDict
from wanx import app

import base64
import json
import hashlib
import os
import pymongo
import random
import re
import string
import time


class User(Document):
    """用户
    """
    collection = DB.users

    CACHED_OBJS = CacheDict(max_len=100, max_age_seconds=5)

    USER_TOKEN = "user:token:%(token)s"  # 用户的token
    RECOMMEND_ATTENTION = "recommend:attention"  # 用户推荐订阅队列
    USER_ASYNC_MSG = 'async_msg:user:%(uid)s'  # 用户消息提醒队列

    def format(self, exclude_fields=[]):
        uid = str(self._id)
        binding = dict(
            qq=True if self.partner_qq and self.partner_qq.get('id') else False,
            weixin=True if self.partner_weixin and self.partner_weixin.get('id') else False,
        )
        status = self.status
        bans = {'live': False, 'video': False, 'comment': False, 'message': False,
                'login': False, 'reason': '', 'lift_at': 0}
        if status and self.bans:
            if self.bans['lift_at'] <= time.time():
                status = 0
            else:
                bans = self.bans

        data = {
            'user_id': uid,
            'migu_id': self.partner_migu and self.partner_migu.get('id'),
            'name': self.name,
            'nickname': self.nickname,
            'logo': urljoin(app.config.get("MEDIA_URL"), self.logo),
            'photo': urljoin(app.config.get("MEDIA_URL"), self.photo),
            'birthday': self.birthday,
            'email': self.email,
            'phone': self.phone,
            'binding': binding,
            'gender': self.gender,
            'favor_count': self.favor_count,
            'subscriptions': self.subscription_count,
            'video_count': self.video_count,
            'follower_count': self.follower_count,
            'following_count': self.following_count,
            'is_followed': False,
            'register_at': self.register_at,
            'signature': self.signature if self.signature else None,
            'announcement': self.announcement if self.announcement else None,
            'status': status,
            'bans': bans,
            'is_match': True if uid in LiveAccount.live_account_uids() else False,
        }
        if 'is_followed' not in exclude_fields:
            _uid = request.authed_user and str(request.authed_user._id)
            data['is_followed'] = uid in FriendShip.following_ids(_uid) if _uid else False
        return data

    def create_model(self):
        # 随机生成用户名
        if not self.nickname:
            self.nickname = self.random_nickname()

        if self.get_by_nickname(self.nickname):
            self.nickname = '%s%s' % (self.nickname, random.randint(10000000, 99999999))

        while self.invalid_nickname(self.nickname):
            self.nickname = self.random_nickname()

        _id = super(User, self).create_model()
        return _id

    @classmethod
    def init(cls):
        doc = super(User, cls).init()
        doc.nickname = ''
        doc.phone = ''
        doc.birthday = 0
        doc.email = ''
        doc.gender = 0
        doc.logo = '/images/2b9/2b9d71591440825ce8dab573b07d38a3.png'
        doc.photo = '/images/2b9/2b9d71591440825ce8dab573b07d38a3.png'
        doc.video_count = 0
        doc.favor_count = 0
        doc.subscription_count = 0
        doc.following_count = 0
        doc.follower_count = 0
        doc.status = const.ONLINE
        doc.update_at = time.time()
        return cls(doc)

    @classmethod
    def invalid_password(cls, password):
        if len(password) < 6 or len(password) > 16:
            return error.PasswordFailed('输入6-16位密码，如为纯数字则不得少于8位')

        if password.isdigit() and len(password) < 8:
            return error.PasswordFailed('输入6-16位密码，如为纯数字则不得少于8位')

        return False

    @classmethod
    def invalid_nickname(cls, nickname):
        p = re.compile(ur"^[a-zA-Z0-9\u4e00-\u9fa5]+$", re.S)
        if not p.match(nickname):
            return error.NicknameInvalid

        # 昵称长度不超过4-20个字符，支持汉字、字母、数字的组合
        if len(nickname.encode('gbk')) < 4 or len(nickname.encode('gbk')) > 20:
            return error.NicknameInvalid

        # 敏感词检查
        if Spam.filter_words(nickname, 'user'):
            return error.InvalidContent('昵称不符合规则')

        # 判断是否被占用
        if User.get_by_nickname(nickname):
            return error.NicknameExists

        return False

    @classmethod
    def search(cls, keyword):
        ids = cls.collection.find(
            {
                'nickname': {'$regex': keyword, '$options': 'i'}
            },
            {'_id': 1}
        )
        ids = [_id['_id'] for _id in ids]
        return list(ids) if ids else list()

    @classmethod
    def random_nickname(cls):
        return ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(12))
        # kw_path = (app.config.get('BASE_DIR') or
        #            os.path.abspath(os.path.join(app.root_path, '../')))
        # fname = os.path.join(kw_path, 'files/nickname.txt')
        # if not os.path.isfile(fname):
        #     return '玩家'
        # lines = []
        # with open(fname, 'r') as f:
        #     lines = f.readlines()
        # line = random.choice(lines)
        # return line.strip('\n')

    @classmethod
    def get_by_name(cls, name):
        user = cls.collection.find_one({"name": name})
        return cls(user) if user else None

    @classmethod
    def get_by_nickname(cls, nickname):
        user = cls.collection.find_one({"nickname": nickname})
        return cls(user) if user else None

    @classmethod
    def get_by_phone(cls, phone):
        user = cls.collection.find_one({"phone": phone})
        return cls(user) if user else None

    @classmethod
    def gen_pwd_hash(cls, password, salt):
        pwd = hashlib.sha256(str(password) + str(salt)).digest()
        return pwd

    @classmethod
    def gen_token(cls, uid):
        ut = base64.b64encode(os.urandom(15), "-.")
        return cls.set_token(ut, uid)

    @classmethod
    def set_token(cls, token, uid):
        if not token or not uid:
            return None
        user = cls.get_one(uid)
        if user.status and user.bans:
            if user.bans["lift_at"] <= time.time():
                data = {
                    '$set': {'status': const.ONLINE, 'bans': {}}
                }
                user.update_model(data)
            elif user.bans["login"]:
                return None

        key = cls.USER_TOKEN % ({'token': token})
        if Redis.setex(key, const.TOKEN_EXPIRE, uid):
            return token
        else:
            return None

    @classmethod
    def recommend_users(cls, uid):
        from wanx.models.game import UserSubGame
        subscriptions = UserSubGame.sub_game_count(uid)
        Redis.zadd(cls.RECOMMEND_ATTENTION, subscriptions, uid)
        Redis.expire(cls.RECOMMEND_ATTENTION, 86400)
        return uid

    @classmethod
    def uid_from_token(cls, token):
        if not token:
            return None
        key = cls.USER_TOKEN % ({'token': token})
        uid = Redis.get(key)
        return uid

    @classmethod
    def login(cls, name, password, login_type='name'):
        if login_type == 'phone':
            user = cls.get_by_phone(name)
        else:
            user = cls.get_by_name(name)
        if not user:
            return None
        if "_password" not in user or "_salt" not in user:
            user._password = const.DEFAULT_PWD.decode("hex")
            user._salt = const.DEFAULT_SALT
        salted_password = cls.gen_pwd_hash(str(password), user._salt)
        d = 0
        for i in range(len(salted_password)):
            # chech will always cost const time.
            d |= ord(user._password[i]) ^ ord(salted_password[i])
        ret = None if d != 0 else cls.get_one(user._id)
        return ret

    @classmethod
    def get_platform_user(cls, platform, openid):
        platform = const.PARTNER[platform]
        key = 'partner_%s' % (platform)
        user = cls.collection.find_one({'%s.id' % (key): openid})
        return cls.get_one(str(user["_id"])) if user else None

    @classmethod
    def create_platform_user(cls, platform, openid, data={}):
        platform = const.PARTNER[platform]
        key = 'partner_%s' % (platform)
        user = User.init()
        user[key] = {'id': openid}
        user.update(data)
        uid = user.create_model()
        return cls.get_one(uid)

    @classmethod
    def change_pwd(cls, user, password):
        salt = os.urandom(const.PWD_HASH_LEN)
        pwd = cls.gen_pwd_hash(password, salt)
        data = {
            '$set': {'_password': Binary(pwd), '_salt': Binary(salt)}
        }
        ret = user.update_model(data)
        return ret

    @classmethod
    def user_recommend_attention(cls):
        try:
            uids = Redis.zrevrange(cls.RECOMMEND_ATTENTION, 0, const.RECOMMEND_ATTENTION_POOL)
        except exceptions.ResponseError:
            uids = []
        return list(uids)

    @classmethod
    def user_bans(cls, uid, lift_at, limits, reason):
        user = cls.get_one(uid)
        bans = dict()
        for i,key in enumerate(["live", "video", "comment", "message", "login"]):
            bans[key] = i in limits
        bans["lift_at"] = lift_at
        bans["reason"] = reason
        user.bans = bans
        data = {
            '$set': {'status': const.OFFLINE, 'bans': bans}
        }
        ret = user.update_model(data)
        return ret


class FriendShip(Document):
    """用户关注关系
    """
    collection = DB.friendship

    FOLLOWER_IDS = 'users:follower:%(uid)s'  # 用户粉丝队列
    FOLLOWING_IDS = 'users:following:%(uid)s'  # 用户关注队列

    def create_model(self):
        _id = super(FriendShip, self).create_model()
        if _id:
            # 更新用户关注数量
            user = User.get_one(str(self.source), check_online=False)
            user.update_model({'$inc': {'following_count': 1}})

            # 更新用户粉丝数量
            user = User.get_one(str(self.target), check_online=False)
            user.update_model({'$inc': {'follower_count': 1}})

            key = self.FOLLOWER_IDS % ({'uid': str(self.target)})
            try:
                if Redis.exists(key):
                    Redis.zadd(key, self.create_at, str(self.source))
            except exceptions.ResponseError:
                Redis.delete(key)

            key = self.FOLLOWING_IDS % ({'uid': str(self.source)})
            try:
                if Redis.exists(key):
                    Redis.zadd(key, self.create_at, str(self.target))
            except exceptions.ResponseError:
                Redis.delete(key)
            # 发送消息到队列
            channel = User.USER_ASYNC_MSG % ({'uid': str(self.target)})
            msg = dict(obj_type='FriendShip', obj_id=str(_id), count=1)
            MRedis.publish(channel, json.dumps(msg))

        return _id

    def delete_model(self):
        ret = super(FriendShip, self).delete_model()
        if ret:
            # 更新用户关注数量
            user = User.get_one(str(self.source), check_online=False)
            user.update_model({'$inc': {'following_count': -1}})

            # 更新用户粉丝数量
            user = User.get_one(str(self.target), check_online=False)
            user.update_model({'$inc': {'follower_count': -1}})

            key = self.FOLLOWER_IDS % ({'uid': str(self.target)})
            try:
                Redis.zrem(key, str(self.source))
            except exceptions.ResponseError:
                Redis.delete(key)
            key = self.FOLLOWING_IDS % ({'uid': str(self.source)})
            try:
                Redis.zrem(key, str(self.target))
            except exceptions.ResponseError:
                Redis.delete(key)
        return ret

    @classmethod
    def init(cls):
        doc = super(FriendShip, cls).init()
        return cls(doc)

    @classmethod
    def get_by_ship(cls, sid, tid):
        fs = cls.collection.find_one({
            'source': ObjectId(sid),
            'target': ObjectId(tid)
        })
        return cls(fs) if fs else None

    @classmethod
    @util.cached_zset(lambda cls, uid: cls.FOLLOWER_IDS % ({'uid': uid}))
    def _load_follower_ids(cls, uid):
        users = list(cls.collection.find(
            {'target': ObjectId(uid)},
            {'source': 1, 'create_at': 1}
        ).sort("create_at", pymongo.DESCENDING))
        ret = list()
        for u in users:
            if User.get_one(str(u['source'])):
                ret.extend([u['create_at'], str(u['source'])])
        return tuple(ret)

    @classmethod
    def follower_ids(cls, uid, page, pagesize, maxs=None):
        key = cls.FOLLOWER_IDS % ({'uid': uid})
        if not Redis.exists(key):
            cls._load_follower_ids(uid)
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
    def follower_count(cls, uid):
        key = cls.FOLLOWER_IDS % ({'uid': uid})
        if not Redis.exists(key):
            cls._load_follower_ids(uid)
        try:
            count = Redis.zcard(key)
        except exceptions.ResponseError:
            count = 0
        return count

    @classmethod
    @util.cached_zset(lambda cls, uid: cls.FOLLOWING_IDS % ({'uid': uid}))
    def _load_following_ids(cls, uid):
        users = list(cls.collection.find(
            {'source': ObjectId(uid)},
            {'target': 1, 'create_at': 1}
        ).sort("create_at", pymongo.DESCENDING))
        ret = list()
        for u in users:
            if User.get_one(str(u['target'])):
                ret.extend([u['create_at'], str(u['target'])])
        return tuple(ret)

    @classmethod
    def following_ids(cls, uid, page=None, pagesize=None, maxs=None):
        key = cls.FOLLOWING_IDS % ({'uid': uid})
        if not Redis.exists(key):
            cls._load_following_ids(uid)
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
    def following_count(cls, uid):
        key = cls.FOLLOWING_IDS % ({'uid': uid})
        if not Redis.exists(key):
            cls._load_following_ids(uid)
        try:
            count = Redis.zcard(key)
        except exceptions.ResponseError:
            count = 0
        return count

    @classmethod
    def contact_ids(cls, uid):
        key1 = cls.FOLLOWER_IDS % ({'uid': uid})
        if not Redis.exists(key1):
            cls._load_follower_ids(uid)

        key2 = cls.FOLLOWING_IDS % ({'uid': uid})
        if not Redis.exists(key2):
            cls._load_following_ids(uid)

        try:
            key = 'tmp:contact:%s' % (uid)
            count = Redis.zinterstore(key, [key1, key2], aggregate='MIN')
            if count:
                uids = Redis.zrange(key, 0, -1)
            else:
                uids = []
        except:
            uids = []
        Redis.delete(key)
        return list(uids)


class UserTrafficLog(Document):
    """用户推广分享
    """
    collection = DB.user_traffic_log

    def format(self):
        data = {
            'traffic_id': str(self._id),
            'status': self.status,
            'create_at': self.create_at,
            'source': str(self.source),
            'release_time': self.release_time,
        }
        return data

    def update_model(self, data={}):
        data['$set']['release_time'] = time.time() if 'release_time' not in data['$set'] \
            else data['$set']['release_time']
        ret = super(UserTrafficLog, self).update_model(data)
        return ret

    @classmethod
    def get_traffic_by_type(cls, source, traffic_type):
        utl = cls.collection.find_one({'source': ObjectId(source), 'traffic_type': traffic_type})
        return cls(utl) if utl else None

    @classmethod
    def get_traffic_by_device(cls, device, traffic_type):
        utl = cls.collection.find_one({'device': device, 'traffic_type': traffic_type,
                                       'status': {'$in': [const.TRAFFIC_SUCCESS,
                                                          const.TRAFFIC_RECEIVED_SUCCESS,
                                                          const.TRAFFIC_RECEIVED_PROCESS]}})
        return cls(utl) if utl else None

    @classmethod
    def traffic_count_by_type(cls, traffic_type):
        count = cls.collection.count({'traffic_type': traffic_type,
                                      'status': {'$in': [const.TRAFFIC_SUCCESS,
                                                         const.TRAFFIC_RECEIVED_SUCCESS,
                                                         const.TRAFFIC_RECEIVED_PROCESS]}})
        return count

    @classmethod
    def get_traffic_by_orderid(cls, order_id):
        utl = cls.collection.find_one({'order_id': order_id})
        return cls(utl) if utl else None


class UserDevice(Document):
    """用户Device
    """
    collection = DB.user_devices

    @classmethod
    def get_by_device(cls, device, appid):
        ud = cls.collection.find_one({'device': device, 'appid': appid})
        return cls(ud) if ud else None

    @classmethod
    def create_or_update_device(cls, device, uid, appid, action):
        ud = cls.get_by_device(device, appid)
        if not ud:
            ud = cls.init()
            ud.device = device
            ud.appid = appid
            ud.user = ObjectId(uid) if uid else None
            ud.update_at = time.time()
            ud.awake_at = time.time()
            ud.create_model()
        else:
            if action == 'awake':
                info = {'awake_at': time.time()}
            else:
                info = {'update_at': time.time()}
            if uid and not ud.user:
                info['user'] = ObjectId(uid)
            ud.update_model({'$set': info})
        return True


class UserShare(Document):
    collection = DB.user_shares
    USER_SHARE_IDS = 'share:user:%(uid)s'

    @classmethod
    @util.cached_zset(lambda cls, uid: cls.USER_SHARE_IDS % {'uid': uid}, snowslide=True)
    def _load_user_shares(cls, uid):
        shares = cls.collection.find({'user': str(uid)},{'_id': 1, 'create_at': 1})
        ids = list()
        for i in shares:
            ids.extend([i['create_at'], str(i['_id'])])
        return tuple(ids)

    @classmethod
    def get_user_shares_by_time(cls, uid, begin_at, end_at):
        key = cls.USER_SHARE_IDS % {'uid': uid}
        if not Redis.exists(key):
            cls._load_user_shares(uid)
        try:
            ids = Redis.zrevrangebyscore(key, end_at, begin_at)
        except exceptions.ResponseError:
            ids = []
        return list(ids)

    def create_model(self):
        key = self.USER_SHARE_IDS % {'uid': self.user}
        Redis.delete(key)
        return super(UserShare, self).create_model()


GROUP_TYPE = (
    (const.WHITELIST_GROUP, u'白名单'),
    (const.BLACKLIST_GROUP, u'黑名单')
)


class Group(Document):
    """用户组
    _id: 用户组ID
    name:用户组名称
    gtype: 用户组类型(whitelist:白名单, blacklist:黑名单)
    memo: 用户组备注
    create_at: 创建时间
    """
    collection = DB.groups
    ALLOWED_LOGIN_ID = 'group:login'

    @classmethod
    def groups_for_admin(cls):
        groups = list(cls.collection.find(
            {},
            {'_id': 1, 'name': 1, 'gtype': 1}
        ))
        group_list = []
        for g in groups:
            desc = util.get_choices_desc(GROUP_TYPE, g['gtype'])
            title = u'%s --- (%s)' % (g['name'], desc) if desc else g['name']
            group_list.append((g['_id'], title))

        return group_list

    @classmethod
    def allowed_login_group(cls):
        key = cls.ALLOWED_LOGIN_ID
        if not Redis.exists(key):
            group = cls.collection.find_one({'name': u'通行证'}, {'_id': 1})
            gid = group['_id'] if group else None
            Redis.set(key, gid)
        else:
            gid = Redis.get(key)
        return gid

    def create_model(self):
        ret = super(Group, self).create_model()
        if ret:
            Redis.delete(self.ALLOWED_LOGIN_ID)
        return ret

    def update_model(self, data={}):
        ret = super(Group, self).update_model(data)
        if ret:
            Redis.delete(self.ALLOWED_LOGIN_ID)
        return ret

    def delete_model(self):
        ret = super(Group, self).delete_model()
        if ret:
            Redis.delete(self.ALLOWED_LOGIN_ID)
        return ret


class UserGroup(Document):
    """用户分组
    _id: 用户分组ID
    group: 用户组ID
    user: 用户ID
    phone: 手机号
    create_at: 创建时间
    """
    collection = DB.user_group

    GROUP_UIDS = 'users:group:%(gid)s'

    def create_model(self):
        _id = super(UserGroup, self).create_model()
        if _id:
            key = self.GROUP_UIDS % ({'gid': str(self.group)})
            Redis.delete(key)

        return _id

    def update_model(self, data={}):
        ret = super(UserGroup, self).update_model(data)
        if ret:
            key = self.GROUP_UIDS % ({'gid': str(self.group)})
            Redis.delete(key)

        return ret

    def delete_model(self):
        ret = super(UserGroup, self).delete_model()
        if ret:
            key = self.GROUP_UIDS % ({'gid': str(self.group)})
            Redis.delete(key)

        return ret

    @classmethod
    @util.cached_list(lambda cls, gid: cls.GROUP_UIDS % ({'gid': gid}))
    def _load_group_uids(cls, gid):
        users = list(cls.collection.find(
            {'group': ObjectId(gid)},
            {'user': 1, 'create_at': 1}
        ))
        uids = [str(u['user']) for u in users]
        return uids

    @classmethod
    def group_user_ids(cls, gid):
        key = cls.GROUP_UIDS % ({'gid': gid})
        if not Redis.exists(key):
            cls._load_group_uids(gid)
        try:
            uids = Redis.lrange(key, 0, -1)
        except exceptions.ResponseError:
            uids = []

        return list(uids)

    @classmethod
    def user_in_group(cls, gid, uid):
        uids = cls.group_user_ids(gid)
        return str(uid) in uids


class LiveAccount(Document):
    """
    比赛直播账号配置
    """
    collection = DB.live_account

    ALL_LIVE_ACCOUNT_IDS = 'live_account:all'  # 所有直播账号列表

    def create_model(self):
        ret = super(LiveAccount, self).create_model()
        if ret:
            Redis.delete(self.ALL_LIVE_ACCOUNT_IDS)
        return ret

    def update_model(self, data={}):
        ret = super(LiveAccount, self).update_model(data)
        if ret:
            Redis.delete(self.ALL_LIVE_ACCOUNT_IDS)
        return ret

    def delete_model(self):
        ret = super(LiveAccount, self).delete_model()
        if ret:
            Redis.delete(self.ALL_LIVE_ACCOUNT_IDS)
        return ret

    @classmethod
    @util.cached_list(lambda cls: cls.ALL_LIVE_ACCOUNT_IDS, snowslide=True)
    def _load_all_live_account_ids(cls):
        versions = list(cls.collection.find(
            {}, {'_id': 1}).sort("create_at", pymongo.ASCENDING))
        _ids = [str(b['_id']) for b in versions]
        return _ids

    @classmethod
    def all_live_account_ids(cls):
        key = cls.ALL_LIVE_ACCOUNT_IDS
        if not Redis.exists(key):
            cls._load_all_live_account_ids()
        try:
            _ids = Redis.lrange(key, 0, -1)
        except exceptions.ResponseError:
            _ids = []
        return list(_ids)

    @classmethod
    def update_data(cls, pk, user_id):
        return cls.collection.update({'_id': pk}, {
            '$set': {'nickname': user_id, 'phone': user_id, 'head_icon': user_id}}, multi=True)

    @classmethod
    def get_by_check(cls, pk):
        doc = cls.collection.find_one({"_id": pk})
        return cls(doc) if doc else None

    @classmethod
    def live_account_uids(cls):

        versions = list(cls.collection.find(
            {}, {'user_id': 1}).sort("create_at", pymongo.ASCENDING))
        u_ids = [str(b['user_id']) for b in versions]
        return u_ids

