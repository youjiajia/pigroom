# -*- coding: utf8 -*-
from bson.objectid import ObjectId
from flask import request
from urlparse import urljoin
from redis import exceptions
from wanx.models import Document
from wanx.base.xredis import Redis
from wanx.base.xmongo import DB, LIVE_DB
from wanx.base import util, const
from wanx.models.user import User
from wanx import app
import pymongo

import time, datetime
import cPickle as cjson


class ActivityConfig(Document):
    """活动配置
    """
    collection = DB.activity_config

    ACTIVITY_CONFIG = "activity:config:%(aid)s"
    ACTIVITY_CONFIG_TYPE = "activity:config:type:%(activity_type)s"
    LIVE_HOT_USER = "live:hot:user:%(aid)s"
    LIVE_NEW_USER = "live:new:user:%(aid)s"

    def format(self):
        data = {
            "activity_id": self._id,
            "description": self.vote_description,
            "vote_text": self.vote_text,
            "voted_text": self.voted_text,
            "activity_url": self.activity_url,
            "sort": self.sort,
            "share_banner": urljoin(app.config.get("MEDIA_URL"), self.share_banner),
            "share_description": self.share_description,
            "share_vote_text": self.share_vote_text,
            "share_voted_text": self.share_voted_text,
            "status": self.status,
            "activity_rule": self.activity_rule if self.activity_rule else None,
            "activity_banner": urljoin(app.config.get("MEDIA_URL"), self.activity_banner),
            "button_join": self.button_join if self.button_join else None,
            "rule_image": urljoin(app.config.get("MEDIA_URL"), self.rule_image),
            "button_lp": self.button_lp if self.button_lp else None,
            "button_tp": self.button_tp if self.button_tp else None,
            "button_tp_link": self.button_tp_link if self.button_tp_link else None
        }

        return data

    def create_model(self):
        ret = super(ActivityConfig, self).create_model()
        if ret:
            Redis.delete(self.ACTIVITY_CONFIG % ({'aid': str(self._id)}))
            Redis.delete(self.ACTIVITY_CONFIG_TYPE % ({'activity_type': self.type}))
            Redis.delete(self.LIVE_HOT_USER % ({'aid': str(self._id)}))
            Redis.delete(self.LIVE_NEW_USER % ({'aid': str(self._id)}))
        return ret

    def update_model(self, data={}):
        ret = super(ActivityConfig, self).update_model(data)
        if ret:
            Redis.delete(self.ACTIVITY_CONFIG % ({'aid': str(self._id)}))
            Redis.delete(self.ACTIVITY_CONFIG_TYPE % ({'activity_type': self.type}))
            Redis.delete(self.LIVE_HOT_USER % ({'aid': str(self._id)}))
            Redis.delete(self.LIVE_NEW_USER % ({'aid': str(self._id)}))
        return ret

    def delete_model(self):
        ret = super(ActivityConfig, self).delete_model()
        if ret:
            Redis.delete(self.ACTIVITY_CONFIG % ({'aid': str(self._id)}))
            Redis.delete(self.ACTIVITY_CONFIG_TYPE % ({'activity_type': self.type}))
            Redis.delete(self.LIVE_HOT_USER % ({'aid': str(self._id)}))
            Redis.delete(self.LIVE_NEW_USER % ({'aid': str(self._id)}))
        return ret

    @property
    def online(self):
        if self.status != const.ACTIVITY_BEGIN:
            return False

        ts = time.time()
        # 还未到上线时间
        if self.begin_at and self.begin_at > ts:
            return False

        # 已到下线时间
        if self.end_at and self.end_at < ts:
            return False

        return True

    @classmethod
    def _load_activity_status(cls, aid, key):
        status = cls.collection.find_one({'_id': ObjectId(aid)}, {'status': 1})
        return Redis.setex(key, 86400, status['status'])

    @classmethod
    def activity_status(cls, aid):
        key = cls.ACTIVITY_CONFIG % ({'aid': str(aid)})
        if not Redis.exists(key):
            cls._load_activity_status(aid, key)
        try:
            activity_status = Redis.get(key)
        except exceptions.ResponseError:
            activity_status = 'begin'
        return activity_status

    @classmethod
    def activity(cls):
        activity = cls.collection.find({}, {'_id': 1, 'name': 1})
        return [(a['_id'], a['name']) for a in activity]

    @classmethod
    def get_by_type(cls, activity_type):
        key = cls.ACTIVITY_CONFIG_TYPE % ({'activity_type': str(activity_type)})
        activity_config = Redis.get(key)
        if activity_config:
            activity_config = cjson.loads(activity_config)
        else:
            activity_config = cls.collection.find({'type': activity_type})
            activity_config = [str(a['_id']) for a in activity_config]
            Redis.setex(key, 86400, cjson.dumps(activity_config, 2))
        return activity_config


class ActivityComment(Document):
    """
    活动评论
    """

    collection = DB.activity_comments

    ACTIVITY_COMMENT_IDS = 'activity:comments:%(aid)s'  # 某个活动的评论队列

    def format(self):
        author = User.get_one(str(self.author), check_online=False)
        uid = request.authed_user and str(request.authed_user._id)
        data = {
            'author': author and author.format(),
            'comment_id': str(self._id),
            'activity_id': self.activity and str(self.activity),
            'content': self.content,
            'create_at': self.create_at,
            'like': self.like or 0,
            'liked': UserLikeActivityComment.get_by_ship(uid, str(
                self._id)) is not None if uid else False,
        }
        return data

    def create_model(self):
        _id = super(ActivityComment, self).create_model()
        if _id:
            key = self.ACTIVITY_COMMENT_IDS % ({'aid': str(self.activity)})
            # 列表为空时key对应的value是一个string
            try:
                if Redis.exists(key):
                    Redis.zadd(key, self.create_at, str(_id))
            except exceptions.ResponseError:
                Redis.delete(key)
        return _id

    def delete_model(self):
        ret = super(ActivityComment, self).delete_model()
        if ret:
            key = self.ACTIVITY_COMMENT_IDS % ({'aid': str(self.activity)})
            try:
                Redis.zrem(key, str(self._id))
            except exceptions.ResponseError:
                Redis.delete(key)
        return ret

    @classmethod
    def init(cls):
        doc = super(ActivityComment, cls).init()
        doc.like = 0
        return cls(doc)

    @classmethod
    @util.cached_zset(lambda cls, activity_id: cls.ACTIVITY_COMMENT_IDS % ({'aid': activity_id}),
                      snowslide=True)
    def _load_activity_comment_ids(cls, activity_id):
        comments = list(cls.collection.find(
            {
                'activity': ObjectId(activity_id),
            },
            {'_id': 1, 'create_at': 1}
        ).sort("create_at", pymongo.DESCENDING))
        ret = list()
        for c in comments:
            if 'create_at' in c:
                ret.extend([c['create_at'], str(c['_id'])])
        return tuple(ret)

    @classmethod
    def activity_comment_ids(cls, activity_id, page=None, pagesize=None, maxs=None):
        """获取活动相关评论的id
        """
        key = cls.ACTIVITY_COMMENT_IDS % ({'aid': activity_id})
        if not Redis.exists(key):
            cls._load_activity_comment_ids(activity_id)
        try:
            if maxs:
                ids = Redis.zrevrangebyscore(key, '(%.6f' % (maxs), '-inf', start=0, num=pagesize)
            else:
                start = (page - 1) * pagesize
                stop = start + pagesize - 1
                ids = Redis.zrevrange(key, start, stop)
        except exceptions.ResponseError:
            # 列表为空时key对应的value是一个string
            ids = []
        return list(ids)

    @classmethod
    def video_comment_count(cls, activity_id):
        key = cls.ACTIVITY_COMMENT_IDS % ({'aid': activity_id})
        if not Redis.exists(key):
            cls._load_video_comment_ids(activity_id)
        try:
            count = Redis.zcard(key)
        except exceptions.ResponseError:
            count = 0
        return count


class UserLikeActivityComment(Document):
    """用户赞的评论
    """
    collection = DB.like_activity_comment

    def create_model(self):
        _id = super(UserLikeActivityComment, self).create_model()
        if _id:
            # 更新评论点赞数
            comment = ActivityComment.get_one(str(self.target), check_online=False)
            comment.update_model({'$inc': {'like': 1}})

        return _id

    def delete_model(self):
        ret = super(UserLikeActivityComment, self).delete_model()
        if ret:
            # 更新评论点赞数
            comment = ActivityComment.get_one(str(self.target), check_online=False)
            comment.update_model({'$inc': {'like': -1}})

        return ret

    @classmethod
    def init(cls):
        doc = super(UserLikeActivityComment, cls).init()
        return cls(doc)

    @classmethod
    def get_by_ship(cls, sid, tid):
        ulav = cls.collection.find_one({
            'source': ObjectId(sid),
            'target': ObjectId(tid)
        })
        return cls(ulav) if ulav else None

    @classmethod
    def load_like_count(cls, cid):
        comment = ActivityComment.get_one(str(cid))
        count = cls.collection.find({'target': ObjectId(cid)}).count()
        comment.update_model({'$set': {'like': count or 0}})
        return count or 0


class ActivityVideo(Document):
    """视频
    """
    collection = DB.activity_videos

    LATEST_VIDEO_IDS = "activity:videos:latest:%(aid)s"  # 最新视频队列
    USER_COMPETE_VIDEO_IDS = "user:compete:%(aid)s:%(uid)s"  # 用户参赛视频
    TOP_COMPETE_VIDEO_IDS = 'top:compete:%(aid)s'  # 活动参赛视频排序
    TOP_VIDEO_END = 'top:video:end:%(aid)s'  # 活动结束时参数视频根据配置排序
    TOP_MANUAL_TOP = 'top:manual:top:%(aid)s'

    def format(self):
        author = User.get_one(str(self.author), check_online=False)
        data = {
            'activity_video': str(self._id),
            'activity_id': self.activity_id,
            'video_id': self.video_id,
            'author': author and author.format(),
            'title': self.title,
            'cover': urljoin(app.config.get("MEDIA_URL"), self.cover),
            'url': '%s/videos/%s/play' % (app.config.get('SERVER_URL'), self.video_id),
            'vv': self.vv,
            'vote': self.vote,
            'like_count': self.like_count,
            'comment_count': self.comment_count,
            'duration': self.duration and int(self.duration),
            'create_at': self.create_at,
            'is_voted': False,
            'top': self.top_author if self.top_author else None
        }

        uid = request.authed_user and str(request.authed_user._id)
        device = request.values.get('device', None)
        is_voted = True if VoteVideo.get_vote(uid, device, self.video_id) else False
        data['is_voted'] = is_voted

        return data

    def create_model(self):
        _id = super(ActivityVideo, self).create_model()
        if _id:
            key = self.LATEST_VIDEO_IDS % ({'aid': str(self.activity_id)})
            try:
                Redis.zadd(key, self.create_at, str(self._id))
            except exceptions.ResponseError:
                Redis.delete(key)

            Redis.delete(self.TOP_COMPETE_VIDEO_IDS % ({'aid': str(self.activity_id)}))

            Redis.delete(self.TOP_VIDEO_END % ({'aid': str(self.activity_id)}))
            Redis.delete(self.TOP_MANUAL_TOP % ({'aid': str(self.activity_id)}))
        return _id

    def update_model(self, data={}):
        obj = super(ActivityVideo, self).update_model(data)
        if obj:
            Redis.delete(self.TOP_COMPETE_VIDEO_IDS % ({'aid': str(self.activity_id)}))

            Redis.delete(self.TOP_VIDEO_END % ({'aid': str(self.activity_id)}))
            Redis.delete(self.TOP_MANUAL_TOP % ({'aid': str(self.activity_id)}))
        return obj

    def delete_model(self):
        ret = super(ActivityVideo, self).delete_model()
        if ret:
            key = self.LATEST_VIDEO_IDS % ({'aid': str(self.activity_id)})
            try:
                Redis.zrem(key, str(self._id))
            except exceptions.ResponseError:
                Redis.delete(key)

            Redis.delete(self.TOP_COMPETE_VIDEO_IDS % ({'aid': str(self.activity_id)}))

            Redis.delete(self.TOP_VIDEO_END % ({'aid': str(self.activity_id)}))
            Redis.delete(self.TOP_MANUAL_TOP % ({'aid': str(self.activity_id)}))
            from wanx.models.video import Video
            video = Video.get_one(str(self.video_id))
            if video:
                video.update_model({'$set': {'activity_ids': []}})
            # 删除所有投票
            vote_ids = VoteVideo.get_by_target(self.video_id)
            for _id in vote_ids:
                vote = VoteVideo.get_one(str(_id))
                vote.delete_model()

        return ret

    @classmethod
    def init(cls):
        doc = super(ActivityVideo, cls).init()
        doc.like_count = 0
        doc.vv = 0
        doc.comment_count = 0
        doc.vote = 0
        return cls(doc)

    @classmethod
    def search(cls, keyword, activity_id):
        ids = cls.collection.find(
            {
                'title': {'$regex': keyword, '$options': 'i'},
                'activity_id': ObjectId(activity_id)
            },
            {'_id': 1}
        ).sort("create_at", pymongo.DESCENDING)
        ids = [_id['_id'] for _id in ids]
        return list(ids) if ids else list()

    @classmethod
    def popular_video_ids(cls, aid, sort, page, pagesize):
        start = (page - 1) * pagesize
        activity_videos = list(cls.collection.find(
            {
                'activity_id': ObjectId(aid),
            }
        ).sort(sort, pymongo.DESCENDING).limit(pagesize).skip(start))
        avids = [str(v['_id']) for v in activity_videos]
        return avids

    @classmethod
    @util.cached_zset(lambda cls, aid: cls.LATEST_VIDEO_IDS % ({'aid': aid}), snowslide=True)
    def _load_latest_video_ids(cls, aid):
        avideo_ids = list(cls.collection.find(
            {'activity_id': ObjectId(aid)},
            {'_id': 1, 'create_at': 1}
        ).sort("create_at", pymongo.DESCENDING))
        ret = list()
        for i in avideo_ids:
            ret.extend([i['create_at'], str(i['_id'])])
        return tuple(ret)

    @classmethod
    def latest_video_ids(cls, aid, pagesize=None, maxs=None):
        key = cls.LATEST_VIDEO_IDS % ({'aid': aid})
        if not Redis.exists(key):
            cls._load_latest_video_ids(aid)
        try:
            avideo_ids = Redis.zrevrangebyscore(key, '(%.6f' % (maxs), '-inf', start=0,
                                                num=pagesize)
        except exceptions.ResponseError:
            avideo_ids = []

        return list(avideo_ids)

    @classmethod
    def user_compete_video_ids(cls, aid, uid):
        videos = list(cls.collection.find(
            {
                'activity_id': ObjectId(aid),
                'author': ObjectId(uid)
            }
        ).sort("create_at", pymongo.DESCENDING))

        return videos

    @classmethod
    @util.cached_list(lambda cls, aid, sort: cls.TOP_COMPETE_VIDEO_IDS % ({'aid': aid}),
                      snowslide=True)
    def _load_top_video_ids(cls, aid, sort):
        top_video_ids = list(cls.collection.find(
            {'activity_id': ObjectId(aid)},
            {'_id': 1}
        ).sort(sort, pymongo.DESCENDING))
        tids = [str(t['_id']) for t in top_video_ids]
        return tids

    @classmethod
    def top_video_ids(cls, aid, sort):
        key = cls.TOP_COMPETE_VIDEO_IDS % ({'aid': aid})
        if not Redis.exists(key):
            cls._load_top_video_ids(aid, sort)
        try:
            tids = Redis.lrange(key, 0, -1)
        except exceptions.ResponseError:
            tids = []

        return list(tids)

    @classmethod
    @util.cached_list(lambda cls, aid, aconfig: cls.TOP_VIDEO_END % ({'aid': aid}), snowslide=True)
    def _load_top_video_end(cls, aid, aconfig={}):
        top_videos = list(cls.collection.find(
            {
                'activity_id': ObjectId(aid),
            }
        ).sort(aconfig['sort'], pymongo.DESCENDING))

        author_dict = dict()
        top_video_ids = list()
        top_num = 1
        max_prize = aconfig['max_prize']  # 单人获奖数量上限
        for tv in top_videos:
            author_id = tv['author']
            if author_id in author_dict and author_dict[author_id] >= max_prize:
                continue

            if author_id not in author_dict:
                author_dict.update({author_id: 1})
            else:
                author_dict[author_id] += 1

            top_video_ids.append(tv['_id'])

            top_num += 1
            if top_num > aconfig['max_rank']:
                break

        return top_video_ids

    @classmethod
    def top_video_end(cls, aid, page=None, pagesize=None, activity_config={}):
        key = cls.TOP_VIDEO_END % ({'aid': aid})
        if not Redis.exists(key):
            cls._load_top_video_end(aid, activity_config)
        try:
            start = (page - 1) * pagesize if page else 0
            stop = (start + pagesize - 1) if pagesize else -1
            tids = Redis.lrange(key, start, stop)
        except exceptions.ResponseError:
            tids = []

        return list(tids)

    @classmethod
    @util.cached_zset(lambda cls, aid: cls.TOP_MANUAL_TOP % ({'aid': aid}))
    def _load_get_manual_top(cls, aid):
        videos = list(cls.collection.find(
            {
                'activity_id': ObjectId(aid),
                'top_author': {'$exists': True}
            }
        ))
        ret = list()
        for i in videos:
            if not i['top_author']:
                continue
            ret.extend([i['top_author'], str(i['_id'])])
        return tuple(ret)

    @classmethod
    def get_manual_top(cls, aid, page=None, pagesize=None, maxs=None):
        key = cls.TOP_MANUAL_TOP % ({'aid': aid})
        if not Redis.exists(key):
            cls._load_get_manual_top(aid)
        try:
            if maxs:
                ids = Redis.zrangebyscore(key, '-inf', '(%.6f' % (maxs), start=0, num=pagesize)
            else:
                start = (page - 1) * pagesize
                stop = start + pagesize - 1
                ids = Redis.zrange(key, start, stop)
        except exceptions.ResponseError:
            ids = []
        return list(ids)

    @classmethod
    def get_activity_video(cls, aid=None, vid=None):
        if not aid:
            avideos = list(cls.collection.find({'video_id': ObjectId(vid)}))
            return avideos
        else:
            avideo = list(cls.collection.find({
                'activity_id': ObjectId(aid),
                'video_id': ObjectId(vid)
            }))
            return avideo

    @classmethod
    def get_activity_video_by_vid(cls, vid):
        activity_video = cls.collection.find_one({'video_id': ObjectId(vid)})
        return cls(activity_video) if activity_video else None

    @classmethod
    def get_activity_video_by_authors(cls, authors, activity_id):
        activity_videos = list(cls.collection.find({'author': {'$in': authors}, 'activity_id': ObjectId(activity_id)}))
        return [str(a['_id']) for a in activity_videos]


class VoteVideo(Document):
    """投票
    """
    collection = DB.vote_video

    def format(self):
        pass

    def create_model(self):
        _id = super(VoteVideo, self).create_model()
        if _id:
            activity_video = ActivityVideo.get_activity_video_by_vid(str(self.target))
            activity_video.update_model({'$inc': {'vote': 1}})
        return _id

    def update_model(self, data={}):
        obj = super(VoteVideo, self).update_model()
        return obj

    def delete_model(self):
        ret = super(VoteVideo, self).delete_model()
        if ret:
            activity_video = ActivityVideo.get_activity_video_by_vid(str(self.target))
            if activity_video:
                activity_video.update_model({'$inc': {'vote': -1}})
        return ret

    @classmethod
    def get_vote(cls, uid=None, device=None, vid=None):
        vote = cls.collection.find_one(
            {
                'target': ObjectId(vid),
                'author': ObjectId(uid),
            }
        )

        return vote

    @classmethod
    def get_by_target(cls, target):
        vote_ids = list(cls.collection.find({'target': ObjectId(target)}))
        ids = [str(v['_id']) for v in vote_ids]
        return ids


class Mteam(Document):
    """
    站队
    """
    collection = DB.mteam

    @classmethod
    def get_mteam_by_tid(cls, tid):
        mteam = cls.collection.find_one({'_id': ObjectId(tid)})
        return cls(mteam) if mteam else None


class VoteMteam(Document):
    """站队投票
    """
    collection = DB.vote_mteam

    def format(self):
        pass

    def create_model(self):
        _id = super(VoteMteam, self).create_model()
        if _id:
            mteam = Mteam.get_mteam_by_tid(str(self.target))
            mteam.update_model({'$inc': {'ticket': 1}})
        return _id

    def update_model(self, data={}):
        obj = super(VoteMteam, self).update_model()
        return obj

    def delete_model(self):
        ret = super(VoteMteam, self).delete_model()
        if ret:
            mteam = Mteam.get_mteam_by_tid(str(self.target))
            if mteam:
                mteam.update_model({'$inc': {'vote': -1}})
        return ret

    @classmethod
    def get_vote(cls, uid=None, device=None, tid=None):
        vote = cls.collection.find_one(
            {
                'target': ObjectId(tid),
                '$or': [{'author': ObjectId(uid)}, {'device': device}]
            }
        )

        return vote

    @classmethod
    def get_by_target(cls, target):
        vote_ids = list(cls.collection.find({'target': ObjectId(target)}))
        ids = [str(v['_id']) for v in vote_ids]
        return ids


class ActivityLiveMaster(Document):
    collection = DB.activity_live_masters

    DUR_MASTERS = 'activity:live:dur:master:%(aid)s'
    NEW_MASTERS = 'activity:live:new:master:%(aid)s'

    def format(self):
        author = User.get_one(str(self.user_id), check_online=False)
        data = {
            'author': author and author.format(),
            'content': self.content,
            'duration': self.duration,
            'create_at': self.create_at,
        }
        return data

    @classmethod
    def check_activity_user(cls, aid, uid):
        res = list(cls.collection.find({'activity_id': aid, 'user_id': uid}))
        uid = res[0]['_id'] if res else None
        return uid

    @classmethod
    @util.cached_zset(lambda cls, aid, end_at: cls.DUR_MASTERS % ({'aid': aid}), snowslide=True)
    def _load_duration_uids(cls, aid, end_at):
        uids = list(cls.collection.find({'activity_id': aid},
                                        {'user_id': 1, 'create_at': 1}))
        user_durations = list()
        for uinfo in uids:
            uid = str(uinfo['user_id'])
            lives = LIVE_DB.event.find(
                {
                    'user_id': uid,
                    'publish_at': {'$gt': uinfo['create_at']},
                    'offline_at': {'$exists': True, '$lt': end_at},
                })
            _duration = 1
            for temp in lives:
                _duration += temp.offline_at - temp.publish_at
            cls.collection.update({'activity_id': aid, 'user_id': uid}, {'$set': {'duration': _duration}})
            user_durations.extend([_duration, str(uinfo['_id'])])
        return tuple(user_durations)

    @classmethod
    def duration_uids(cls, aid, end_at, page=None, pagesize=None, maxs=None):
        key = cls.DUR_MASTERS % ({'aid': aid})
        if not Redis.exists(key):
            cls._load_duration_uids(aid, end_at)
        try:
            if maxs:
                ids = Redis.zrevrangebyscore(key, '(%.6f' % (maxs), '-inf', start=0, num=pagesize)
            else:
                start = (page - 1) * pagesize
                stop = start + pagesize - 1
                ids = Redis.zrevrange(key, start, stop)
        except exceptions.ResponseError:
            ids = []
        return ids

    @classmethod
    @util.cached_zset(lambda cls, aid, end_at: cls.NEW_MASTERS % ({'aid': aid}), snowslide=True)
    def _load_latest_uids(cls, aid, end_at):
        uids = list(cls.collection.find({'activity_id': aid},
                                        {'user_id': 1, 'create_at': 1}))
        user_latest = list()
        for uinfo in uids:
            user_latest.extend([uinfo['create_at'], str(uinfo['_id'])])
        return user_latest

    @classmethod
    def latest_uids(cls, aid, end_at, page=None, pagesize=None, maxs=None):
        key = cls.NEW_MASTERS % ({'aid': aid})
        if not Redis.exists(key):
            cls._load_latest_uids(aid, end_at)
        try:
            if maxs:
                ids = Redis.zrevrangebyscore(key, '(%.6f' % (maxs), '-inf', start=0, num=pagesize)
            else:
                start = (page - 1) * pagesize
                stop = start + pagesize - 1
                ids = Redis.zrevrange(key, start, stop)
        except exceptions.ResponseError:
            ids = []
        return ids

    @classmethod
    def clear_redis_by_user(cls, uid):
        for alm in cls.get_by_user(uid):
            cls.clear_redis(alm['activity_id'])

    @classmethod
    def clear_redis(cls, aid):
        key_dur = cls.DUR_MASTERS % ({'aid': aid})
        key_new = cls.NEW_MASTERS % ({'aid': aid})
        Redis.delete([key_dur, key_new])


class ShareActivityConfig(Document):
    """活动配置
    """
    collection = DB.share_activity_config
    USED_TODAY = 'activity:share:used:%(day)s:%(aid)s'

    def format(self, uid, device):
        user = User.get_one(uid)
        shared = False
        if user:
            shared = UserShareActivityLog.check_user_activity(self._id, user.phone, device)
        today_used = int(ShareActivityConfig.get_used_today(self._id))
        today_left = max(0, min(self.daily_num - today_used, self.left_num))

        data = {
            'id': str(self._id),
            'today_left': today_left,
            'shared': shared,
            'begin_at': self.begin_at,
            'end_at': self.end_at,
            'icon': urljoin(app.config.get("MEDIA_URL"), self.icon),
            'title': self.title,
        }
        return data

    def get_left_today(self):
        used = self.get_used_today(str(self._id))
        left = max(0, min(self.daily_num - used, self.left_num))
        return left

    @classmethod
    def get_used_today(cls, aid):
        today = datetime.date.today().strftime('%y%m%d')
        key = cls.USED_TODAY % ({'day': today, 'aid': aid})
        if not Redis.exists(key):
            Redis.set(key, 0)
            Redis.expire(key, 60 * 60 * 24)
        return int(Redis.get(key))

    @classmethod
    def incr_used_today(cls, aid):
        today = datetime.date.today().strftime('%y%m%d')
        key = cls.USED_TODAY % ({'day': today, 'aid': aid})
        Redis.incr(key, amount=1)

    @property
    def online(self):
        ts = time.time()
        # 还未到上线时间
        if self.begin_at and self.begin_at > ts:
            return False

        # 已到下线时间
        if self.end_at and self.end_at < ts:
            return False

        return True


class UserShareActivityLog(Document):
    collection = DB.user_share_activity_logs
    USER_ACTIVITY = 'activity:share:%(aid)s:%(xid)s'

    @classmethod
    def _get_user_activity(cls, aid, key, xid):
        query = {
                key: xid
            }
        if aid != 'all':
            query.update({'activity': ObjectId(aid)})
        cnt = cls.collection.find(query).count()
        return cnt

    @classmethod
    def check_user_activity(cls, aid, phone, device):
        # 每个手机号码/设备ID在此类活动历史只能参与1次活动，所以将aid强制改为all
        aid = 'all'
        for k, xid in {'phone': phone, 'device': device}.iteritems():
            key = cls.USER_ACTIVITY % ({'aid': aid, 'xid': xid})
            if not Redis.exists(key):
                cnt = cls._get_user_activity(aid, k, xid)
                Redis.set(key, cnt, 60*60*24)
            cnt = int(Redis.get(key))
            if cnt:
                return True
        return False

    @classmethod
    def get_used_today(cls, aid):
        today = datetime.date.today()
        start = time.mktime(today.timetuple())
        end = start + 60 * 60 * 24
        cnt = cls.collection.find({
            'activity': ObjectId(aid),
            'create_at': {'$gte': start, '$lte': end}
        }).count()
        return cnt

    def create_model(self):
        aid = 'all'
        phone = self.phone
        device = self.device
        for k, xid in {'phone': phone, 'device': device}.iteritems():
            key = self.USER_ACTIVITY % ({'aid': aid, 'xid': xid})
            Redis.delete(key)
        return super(UserShareActivityLog, self).create_model()

