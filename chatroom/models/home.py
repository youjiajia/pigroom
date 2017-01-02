# -*- coding: utf8 -*-
from bson.objectid import ObjectId
from urlparse import urljoin
from redis import exceptions
from wanx.models import Document, BaseModel
from wanx.base.xredis import Redis
from wanx.base.xmongo import DB
from wanx.base import util, const
from wanx.base.util import datetime2str, str2timestamp
from wanx.base.cachedict import CacheDict
from wanx import app
from wanx.models.user import Group, UserGroup

import pymongo
import time
import peewee as pw


class LaunchAds(Document):
    """开屏广告
    """
    collection = DB.launch_ads

    CACHED_OBJS = CacheDict(max_len=100, max_age_seconds=5)

    ALL_AD_IDS = 'launchads:all'  # 所有开屏广告信息

    def format(self):
        data = {
            'ad_id': str(self._id),
            'image': urljoin(app.config.get("MEDIA_URL"), self.image),
            'duration': self.duration,
            'action': self.action,
            'rate': self.rate,
            'create_at': self.create_at,
            'expire_at': self.expire_at
        }
        return data

    @property
    def online(self):
        _is_online = super(LaunchAds, self).online
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

    def create_model(self):
        ret = super(LaunchAds, self).create_model()
        if ret:
            Redis.delete(self.ALL_AD_IDS)
        return ret

    def update_model(self, data={}):
        ret = super(LaunchAds, self).update_model(data)
        if ret:
            Redis.delete(self.ALL_AD_IDS)
        return ret

    def delete_model(self):
        ret = super(LaunchAds, self).delete_model()
        if ret:
            Redis.delete(self.ALL_AD_IDS)
        return ret

    @classmethod
    @util.cached_list(lambda cls: cls.ALL_AD_IDS, snowslide=True)
    def _load_all_ad_ids(cls):
        ads = list(cls.collection.find(
            {'expire_at': {'$gte': time.time()}},
            {'_id': 1}
        ))
        ad_ids = [str(ad['_id']) for ad in ads]
        return ad_ids

    @classmethod
    def all_ad_ids(cls):
        key = cls.ALL_AD_IDS
        if not Redis.exists(key):
            cls._load_all_ad_ids()
        try:
            ad_ids = Redis.lrange(key, 0, -1)
        except exceptions.ResponseError:
            ad_ids = []
        return list(ad_ids)


class Banner(Document):
    """Banner广告
    """
    collection = DB.top_banner

    CACHED_OBJS = CacheDict(max_len=100, max_age_seconds=5)

    ALL_BANNER_IDS = 'banners:all'  # 所有广告banner列表
    ALL_BANNERS_BY_VERSION = 'banners:all:version'

    def format(self):
        data = {
            'banner_id': str(self._id),
            'image': urljoin(app.config.get("MEDIA_URL"), self.image),
            'create_at': self.create_at,
            'duration': self.duration,
            'action': self.action,
            'expire_at': self.expire_at
        }
        return data

    @property
    def online(self):
        _is_online = super(Banner, self).online
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

    def create_model(self):
        ret = super(Banner, self).create_model()
        if ret:
            Redis.delete(self.ALL_BANNER_IDS)
            Redis.delete(self.ALL_BANNERS_BY_VERSION)
        return ret

    def update_model(self, data={}):
        ret = super(Banner, self).update_model(data)
        if ret:
            Redis.delete(self.ALL_BANNER_IDS)
            Redis.delete(self.ALL_BANNERS_BY_VERSION)
        return ret

    def delete_model(self):
        ret = super(Banner, self).delete_model()
        if ret:
            Redis.delete(self.ALL_BANNER_IDS)
            Redis.delete(self.ALL_BANNERS_BY_VERSION)
        return ret

    @classmethod
    @util.cached_list(lambda cls: cls.ALL_BANNER_IDS, snowslide=True)
    def _load_all_banner_ids(cls):
        banners = list(cls.collection.find(
            {'expire_at': {'$gte': time.time()}},
            {'_id': 1}
        ).sort("order", pymongo.ASCENDING))
        bids = [str(b['_id']) for b in banners]
        return bids

    @classmethod
    def all_banner_ids(cls):
        key = cls.ALL_BANNER_IDS
        if not Redis.exists(key):
            cls._load_all_banner_ids()
        try:
            bids = Redis.lrange(key, 0, -1)
        except exceptions.ResponseError:
            bids = []
        return list(bids)

    @classmethod
    @util.cached_list(lambda cls: cls.ALL_BANNERS_BY_VERSION, snowslide=True)
    def _load_all_banner_version(cls):
        banners = list(cls.collection.find(
            {'expire_at': {'$gte': time.time()},
             '$and': [{'version_code_mix': {'$exists': True}},
                      {'version_code_mix': {'$lte': const.BANNER_VERSION}}]
             },
            {'_id': 1}
        ).sort("order", pymongo.ASCENDING))
        bids = [str(b['_id']) for b in banners]
        return bids

    @classmethod
    def all_banners_by_version(cls):
        key = cls.ALL_BANNERS_BY_VERSION
        if not Redis.exists(key):
            cls._load_all_banner_version()
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


class BannerSdk(Document):
    """SDK活动
    """
    collection = DB.sdk_banner

    CACHED_OBJS = CacheDict(max_len=100, max_age_seconds=5)

    ALL_SDK_BANNER_IDS = 'sdk:banners:all'  # 所有广告banner列表

    def format(self):
        data = {
            'banner_id': str(self._id),
            'vertical_image': urljoin(app.config.get("MEDIA_URL"), self.vertical_image),
            'transverse_image': urljoin(app.config.get("MEDIA_URL"), self.transverse_image),
            'create_at': self.create_at,
            'duration': self.duration,
            'action': self.action,
            'expire_at': self.expire_at
        }
        return data

    @property
    def online(self):
        _is_online = super(BannerSdk, self).online
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

    def create_model(self):
        ret = super(BannerSdk, self).create_model()
        if ret:
            Redis.delete(self.ALL_SDK_BANNER_IDS)
        return ret

    def update_model(self, data={}):
        ret = super(BannerSdk, self).update_model(data)
        if ret:
            Redis.delete(self.ALL_SDK_BANNER_IDS)
        return ret

    def delete_model(self):
        ret = super(BannerSdk, self).delete_model()
        if ret:
            Redis.delete(self.ALL_SDK_BANNER_IDS)
        return ret

    @classmethod
    @util.cached_list(lambda cls: cls.ALL_SDK_BANNER_IDS, snowslide=True)
    def _load_all_sdk_banner_ids(cls):
        banners = list(cls.collection.find(
            {'expire_at': {'$gte': time.time()}},
            {'_id': 1}
        ).sort("order", pymongo.ASCENDING))
        bids = [str(b['_id']) for b in banners]
        return bids

    @classmethod
    def all_sdk_banner_ids(cls):
        key = cls.ALL_SDK_BANNER_IDS
        if not Redis.exists(key):
            cls._load_all_sdk_banner_ids()
        try:
            bids = Redis.lrange(key, 0, -1)
        except exceptions.ResponseError:
            bids = []
        return list(bids)


class HomeCategory(Document):
    """首页分类模块
    """
    collection = DB.home_category
    ALL_CATEGORYS_IDS = 'homecate:all'  # 所有分类模块列表

    def format(self):
        data = {
            'name': self.name,
            'icon': urljoin(app.config.get("MEDIA_URL"), self.icon) if self.icon else None,
            'action': self.action,
            'ctype': self.ctype
        }
        return data

    def create_model(self):
        ret = super(HomeCategory, self).create_model()
        if ret:
            Redis.delete(self.ALL_CATEGORYS_IDS)
        return ret

    def update_model(self, data={}):
        ret = super(HomeCategory, self).update_model(data)
        if ret:
            Redis.delete(self.ALL_CATEGORYS_IDS)
        return ret

    def delete_model(self):
        ret = super(HomeCategory, self).delete_model()
        if ret:
            Redis.delete(self.ALL_CATEGORYS_IDS)
        return ret

    @classmethod
    @util.cached_list(lambda cls: cls.ALL_CATEGORYS_IDS, snowslide=True)
    def _load_all_category_ids(cls):
        cates = list(cls.collection.find({}, {'_id': 1}).sort("order", pymongo.ASCENDING))
        cate_ids = [str(cate['_id']) for cate in cates]
        return cate_ids

    @classmethod
    def all_category_ids(cls):
        key = cls.ALL_CATEGORYS_IDS
        if not Redis.exists(key):
            cls._load_all_category_ids()
        try:
            cate_ids = Redis.lrange(key, 0, -1)
        except exceptions.ResponseError:
            cate_ids = []
        return list(cate_ids)

    @classmethod
    def all_categories_for_admin(cls):
        cates = list(cls.collection.find({}, {'_id': 1, 'name': 1}))
        return [(c['_id'], c['name']) for c in cates]


class HomeCategoryConfig(Document):
    """首页分类配置
    """
    collection = DB.home_category_config
    CATEGORY_OBJ_IDS = 'home_category:%(cate_id)s'

    def create_model(self):
        ret = super(HomeCategoryConfig, self).create_model()
        if ret:
            key = self.CATEGORY_OBJ_IDS % ({'cate_id': str(self.category)})
            Redis.delete(key)
        return ret

    def update_model(self, data={}):
        ret = super(HomeCategoryConfig, self).update_model(data)
        if ret:
            key = self.CATEGORY_OBJ_IDS % ({'cate_id': str(self.category)})
            Redis.delete(key)
            if self.category != ret.category:
                key = self.CATEGORY_OBJ_IDS % ({'cate_id': str(ret.category)})
                Redis.delete(key)
        return ret

    def delete_model(self):
        ret = super(HomeCategoryConfig, self).delete_model()
        if ret:
            key = self.CATEGORY_OBJ_IDS % ({'cate_id': str(self.category)})
            Redis.delete(key)
        return ret

    @classmethod
    @util.cached_list(lambda cls, cate_id: cls.CATEGORY_OBJ_IDS % ({'cate_id': cate_id}),
                      snowslide=True)
    def _load_category_object_ids(cls, cate_id):
        cates = list(cls.collection.find(
            {'category': ObjectId(cate_id)},
            {'target': 1}
        ).sort("order", pymongo.ASCENDING))
        cate_ids = [str(cate['target']) for cate in cates]
        return cate_ids

    @classmethod
    def category_object_ids(cls, cate_id):
        key = cls.CATEGORY_OBJ_IDS % ({'cate_id': cate_id})
        if not Redis.exists(key):
            cls._load_category_object_ids(cate_id)
        try:
            cate_ids = Redis.lrange(key, 0, -1)
        except exceptions.ResponseError:
            cate_ids = []
        return list(cate_ids)


class Popup(Document):
    """弹窗
    """

    collection = DB.popup
    POPUP_PLATFORM = "popup:os:%(os)s"

    def format(self):
        data = {
            'popup_id': self._id,
            'image': urljoin(app.config.get("MEDIA_URL"), self.image),
            'image_link': self.image_link,
            'image_link_type': self.image_link_type,
            'button_text': self.button_text,
            'button_link': self.button_link,
            'show_button': self.show_button
        }
        return data

    @property
    def online(self):
        _is_online = super(Popup, self).online
        if not _is_online:
            _is_online = False

        ts = time.time()
        # 还未到上线时间
        if self.begin_at and self.begin_at > ts:
            _is_online = False

        # 已到下线时间
        if self.expire_at and self.expire_at < ts:
            _is_online = False

        if _is_online and self.is_push:
            return True

        return False

    @property
    def is_push(self):
        if not self.push_begin_at or not self.push_expire_at:
            return True

        ts = int(time.time())
        date_str = datetime2str(ts)
        push_begin_at = str2timestamp(' '.join([date_str, self.push_begin_at]))
        push_expire_at = str2timestamp(' '.join([date_str, self.push_expire_at]))

        if push_expire_at >= ts and push_begin_at <= ts:
            return True

        return False

    def create_model(self):
        _id = super(Popup, self).create_model()
        if _id:
            key = self.POPUP_PLATFORM % ({'os': self.os})
            Redis.delete(key)
        return _id

    def update_model(self, data={}):
        obj = super(Popup, self).update_model(data)
        if obj:
            key = self.POPUP_PLATFORM % ({'os': self.os})
            Redis.delete(key)
        return obj

    def delete_model(self):
        ret = super(Popup, self).delete_model()
        if ret:
            key = self.POPUP_PLATFORM % ({'os': self.os})
            Redis.delete(key)
        return ret

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

    @classmethod
    @util.cached_list(lambda cls, os: cls.POPUP_PLATFORM % ({'os': os}))
    def _load_popup_platform_ids(cls, os):
        popup = list(cls.collection.find(
            {'os': os},
            {'_id': 1, 'create_at': 1}
        ))
        pids = [str(p['_id']) for p in popup]
        return pids

    @classmethod
    def popup_platform_ids(cls, os):
        key = cls.POPUP_PLATFORM % ({'os': os})
        if not Redis.exists(key):
            cls._load_popup_platform_ids(os)
        try:
            pids = Redis.lrange(key, 0, -1)
        except exceptions.ResponseError:
            pids = []

        return list(pids)


class PopupLog(Document):
    """弹窗记录
    """
    collection = DB.popup_log

    @classmethod
    def get_by_device(cls, device):
        pd = list(cls.collection.find({'device': device}))
        return [p['target'] for p in pd]


class Channels(Document):
    """推广渠道
    """
    collection = DB.channels

    ALL_CHANNELS_IDS = 'channels:all'

    def create_model(self):
        _id = super(Channels, self).create_model()
        if _id:
            key = self.ALL_CHANNELS_IDS
            Redis.delete(key)

        return _id

    def update_model(self, data={}):
        ret = super(Channels, self).update_model(data)
        if ret:
            key = self.ALL_CHANNELS_IDS
            Redis.delete(key)

        return ret

    def delete_model(self):
        ret = super(Channels, self).delete_model()
        if ret:
            key = self.ALL_CHANNELS_IDS
            Redis.delete(key)

        return ret

    @classmethod
    @util.cached_list(lambda cls: cls.ALL_CHANNELS_IDS, snowslide=True)
    def _load_all_channels_ids(cls):
        channels = list(cls.collection.find({}, {'_id': 1}))
        _ids = [str(c['_id']) for c in channels]
        return _ids

    @classmethod
    def all_channels_ids(cls):
        key = cls.ALL_CHANNELS_IDS
        if not Redis.exists(key):
            cls._load_all_channels_ids()
        try:
            _ids = Redis.lrange(key, 0, -1)
        except exceptions.ResponseError:
            _ids = []
        return list(_ids)


class Share(Document):
    """
    分享配置
    """
    collection = DB.share

    @classmethod
    def get_by_game(cls, share_config='分享游戏'):
        share = cls.collection.find_one({"share_config": share_config})
        return cls(share) if share else None

    @classmethod
    def get_by_self_live(cls, share_config='分享自己直播间'):
        share = cls.collection.find_one({"share_config": share_config})
        return cls(share) if share else None

    @classmethod
    def get_by_others_live(cls, share_config='分享他人直播间'):
        share = cls.collection.find_one({"share_config": share_config})
        return cls(share) if share else None

    @classmethod
    def get_by_self_video(cls, share_config='分享自己视频'):
        share = cls.collection.find_one({"share_config": share_config})
        return cls(share) if share else None

    @classmethod
    def get_by_others_video(cls, share_config='分享他人视频'):
        share = cls.collection.find_one({"share_config": share_config})
        return cls(share) if share else None


class FixedBanner(Document):
    collection = DB.fixed_banner

    CACHED_OBJS = CacheDict(max_len=100, max_age_seconds=5)

    ALL_BANNER_IDS = 'fixed_banners:all'  # 所有固定banner列表
    ALL_BANNERS_BY_VERSION = 'fixed_banners:all:version'

    def format(self):
        data = {
            'banner_id': str(self._id),
            'image': urljoin(app.config.get("MEDIA_URL"), self.image),
            'create_at': self.create_at,
            'position': self.position,
            'action': self.url,
            'expire_at': self.expire_at
        }
        return data

    @property
    def online(self):
        _is_online = super(FixedBanner, self).online
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
    @util.cached_list(lambda cls: cls.ALL_BANNER_IDS, snowslide=True)
    def _load_all_banner_ids(cls):
        banners = list(cls.collection.find(
            {'expire_at': {'$gte': time.time()}},
            {'_id': 1}
        ).sort("order", pymongo.ASCENDING))
        bids = [str(b['_id']) for b in banners]
        return bids

    @classmethod
    def all_banner_ids(cls):
        key = cls.ALL_BANNER_IDS
        if not Redis.exists(key):
            cls._load_all_banner_ids()
        try:
            bids = Redis.lrange(key, 0, -1)
        except exceptions.ResponseError:
            bids = []
        return list(bids)

    def create_model(self):
        ret = super(FixedBanner, self).create_model()
        if ret:
            Redis.delete(self.ALL_BANNER_IDS)
        return ret

    def update_model(self, data={}):
        ret = super(FixedBanner, self).update_model(data)
        if ret:
            Redis.delete(self.ALL_BANNER_IDS)
        return ret

    def delete_model(self):
        ret = super(FixedBanner, self).delete_model()
        if ret:
            Redis.delete(self.ALL_BANNER_IDS)
        return ret

    @classmethod
    @util.cached_list(lambda cls: cls.ALL_BANNERS_BY_VERSION, snowslide=True)
    def _load_all_banner_version(cls):
        banners = list(cls.collection.find(
            {'expire_at': {'$gte': time.time()},
             '$and': [{'version_code_mix': {'$exists': True}},
                      {'version_code_mix': {'$gte': const.BANNER_VERSION}}]
             },
            {'_id': 1}
        ).sort("order", pymongo.ASCENDING))
        bids = [str(b['_id']) for b in banners]
        return bids

    @classmethod
    def all_banners_by_version(cls):
        key = cls.ALL_BANNERS_BY_VERSION
        if not Redis.exists(key):
            cls._load_all_banner_version()
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

    @classmethod
    def check_crash(cls, banner, _id=None):
        f = {'os': banner['os'], 'position': banner['position'], 'group': banner['group']}
        if _id:
            f.update({'_id': {"$ne": ObjectId(_id)}})
        banners = cls.collection.find(f)
        if not banners:
            return False, ""

        def check_interval_crash(b1, e1, b2, e2):
            if b1 <= b2 <= e1:
                return True
            elif b1 <= e2 <= e1:
                return True
            elif b2 <= b1 <= e2:
                return True
            elif b2 <= e1 <= e2:
                return True
            else:
                return False

        def check_array_crash(array1, array2):
            if not array1 or not array2:
                return True
            array = array1 + array2
            return set(array).__len__() != array.__len__()

        for eb in banners:
            version_crash = check_interval_crash(eb['version_code_mix'],
                                                 eb['version_code_max'],
                                                 banner['version_code_mix'],
                                                 banner['version_code_max'])
            time_crash = check_interval_crash(eb['begin_at'], eb['expire_at'],
                                              banner['begin_at'], banner['expire_at'])
            channel_crash = check_array_crash(eb['channels'], banner['channels'])
            province_crash = check_array_crash(eb['province'], banner['province'])

            if all([version_crash, time_crash, channel_crash, province_crash]):
                crashs = []
                if version_crash:
                    crashs.append(u"[版本]")
                if time_crash:
                    crashs.append(u"[时间]")
                if channel_crash:
                    crashs.append(u"[渠道]")
                if province_crash:
                    crashs.append(u"[省份]")
                return True, u"、".join(crashs)

        return False, ""


class BugReport(BaseModel):
    report_id = pw.PrimaryKeyField(verbose_name='错误报告ID')
    err_type = pw.CharField(max_length=64, verbose_name='错误类型')
    exception = pw.CharField(max_length=64, verbose_name='异常类型')
    phone_model = pw.CharField(max_length=32, verbose_name='手机型号')
    os_version = pw.CharField(max_length=32, verbose_name='系统版本')
    phone_number = pw.CharField(max_length=16, verbose_name='手机号码')
    app_version = pw.CharField(max_length=16, verbose_name='APP版本')
    err_msg = pw.TextField(verbose_name='错误信息')
    err_app = pw.IntegerField(default=0, verbose_name='发生APP')
    extention = pw.TextField(verbose_name='自定义信息')

    class Meta:
        db_table = 'bug_report'

    @classmethod
    def add_report(cls, argvs):
        (err_type, exception, phone_model, os_version, phone_number,
         app_version, err_msg, err_app, extention) = argvs

        data = dict(err_type=err_type, exception=exception, phone_model=phone_model, os_version=os_version,
                   phone_number=phone_number, app_version=app_version, err_msg=err_msg,
                   err_app=err_app, extention=extention)

        cls.insert(data).execute()

        return True


class H5Counter(Document):
    H5KEY = 'h5:{0}'

    @classmethod
    def update_counter(cls, countid):
        key = cls.H5KEY.format(countid)
        if not Redis.exists(key):
            num = 1
        else:
            num = int(Redis.get(key)) + 1
            # 限制数字不能超过八位
            if num > 99999999:
                num = 1
        Redis.set(key, num)
        return num
