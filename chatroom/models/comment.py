# -*- coding: utf8 -*-
from bson.objectid import ObjectId
from flask import request
from redis import exceptions
from wanx.models import Document
from wanx.base.xredis import Redis
from wanx.base.xmongo import DB
from wanx.base import util, const
from wanx.base.cachedict import CacheDict
from wanx.models.user import User

import pymongo


class Comment(Document):
    """评论
    """
    collection = DB.comments

    CACHED_OBJS = CacheDict(max_len=100, max_age_seconds=5)

    VIDEO_COMMENT_IDS = 'comments:video:%(vid)s'  # 某个视频的评论队列

    def format(self):
        author = User.get_one(str(self.author), check_online=False)
        uid = request.authed_user and str(request.authed_user._id)
        data = {
            'author': author and author.format(exclude_fields=['is_followed']),
            'comment_id': str(self._id),
            'video_id': self.video and str(self.video),
            'content': self.content,
            'create_at': self.create_at,
            'reply': self.reply or 0,
            'like': self.like or 0,
            'liked': UserLikeComment.get_by_ship(uid, str(self._id)) is not None if uid else False,
        }
        return data

    def create_model(self):
        _id = super(Comment, self).create_model()
        if _id:
            # 更新视频评论数
            from wanx.models.video import Video
            video = Video.get_one(str(self.video), check_online=False)
            video.update_model({'$inc': {'comment_count': 1}})

            key = self.VIDEO_COMMENT_IDS % ({'vid': str(self.video)})
            # 列表为空时key对应的value是一个string
            try:
                if Redis.exists(key):
                    Redis.zadd(key, self.create_at, str(_id))
            except exceptions.ResponseError:
                Redis.delete(key)
        return _id

    def delete_model(self):
        ret = super(Comment, self).delete_model()
        if ret:
            # 更新视频评论数
            from wanx.models.video import Video
            video = Video.get_one(str(self.video), check_online=False)
            video.update_model({'$inc': {'comment_count': -1}})

            key = self.VIDEO_COMMENT_IDS % ({'vid': str(self.video)})
            try:
                Redis.zrem(key, str(self._id))
            except exceptions.ResponseError:
                Redis.delete(key)
            # 删除全部回复
            Reply.delete_comment_replies(str(self._id))
        return ret

    @classmethod
    def init(cls):
        doc = super(Comment, cls).init()
        doc.like = 0
        doc.reply = 0
        doc.status = const.ONLINE
        return cls(doc)

    @classmethod
    @util.cached_zset(lambda cls, video_id: cls.VIDEO_COMMENT_IDS % ({'vid': video_id}),
                      snowslide=True)
    def _load_video_comment_ids(cls, video_id):
        comments = list(cls.collection.find(
            {
                'video': ObjectId(video_id),
                '$or': [{'status': {'$exists': False}}, {'status': 0}]
            },
            {'_id': 1, 'create_at': 1}
        ).sort("create_at", pymongo.DESCENDING))
        ret = list()
        for c in comments:
            if 'create_at' in c:
                ret.extend([c['create_at'], str(c['_id'])])
        return tuple(ret)

    @classmethod
    def video_comment_ids(cls, video_id, page=None, pagesize=None, maxs=None):
        """获取视频相关评论的id
        """
        key = cls.VIDEO_COMMENT_IDS % ({'vid': video_id})
        if not Redis.exists(key):
            cls._load_video_comment_ids(video_id)
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
    def video_comment_count(cls, video_id):
        key = cls.VIDEO_COMMENT_IDS % ({'vid': video_id})
        if not Redis.exists(key):
            cls._load_video_comment_ids(video_id)
        try:
            count = Redis.zcard(key)
        except exceptions.ResponseError:
            count = 0
        return count


class UserLikeComment(Document):
    """用户赞的评论
    """
    collection = DB.like_comment

    def create_model(self):
        _id = super(UserLikeComment, self).create_model()
        if _id:
            # 更新评论点赞数
            comment = Comment.get_one(str(self.target), check_online=False)
            comment.update_model({'$inc': {'like': 1}})

        return _id

    def delete_model(self):
        ret = super(UserLikeComment, self).delete_model()
        if ret:
            # 更新评论点赞数
            comment = Comment.get_one(str(self.target), check_online=False)
            comment.update_model({'$inc': {'like': -1}})

        return ret

    @classmethod
    def init(cls):
        doc = super(UserLikeComment, cls).init()
        return cls(doc)

    @classmethod
    def get_by_ship(cls, sid, tid):
        ulv = cls.collection.find_one({
            'source': ObjectId(sid),
            'target': ObjectId(tid)
        })
        return cls(ulv) if ulv else None

    @classmethod
    def load_like_count(cls, cid):
        comment = Comment.get_one(str(cid))
        count = cls.collection.find({'target': ObjectId(cid)}).count()
        comment.update_model({'$set': {'like': count or 0}})
        return count or 0


class Reply(Document):
    """评论回复
    owner: 回复者
    reply: 被用户回复的评论回复
    comment: 所属评论ID
    content: 内容
    create_at: 创建时间
    """
    collection = DB.replies

    CACHED_OBJS = CacheDict(max_len=100, max_age_seconds=30)

    COMMENT_REPLY_IDS = 'reply:comment:%(cid)s'  # 评论的回复队列

    def format(self):
        _reply = Reply.get_one(str(self.reply), check_online=False)
        from_user = User.get_one(str(self.owner), check_online=False)
        to_user = User.get_one(str(_reply.owner), check_online=False) if _reply else None
        data = {
            'reply_id': str(self._id),
            'reply_from': from_user and from_user.format(exclude_fields=['is_followed']),
            'reply_to': to_user and to_user.format(exclude_fields=['is_followed']),
            'content': self.content,
            'reply_count': self.reply_count or 0,
            'create_at': self.create_at
        }
        return data

    def create_model(self):
        _id = super(Reply, self).create_model()
        if _id:
            # 更新评论回复数
            comment = Comment.get_one(str(self.comment), check_online=False)
            comment.update_model({'$inc': {'reply': 1}})
            # 更新回复的回复数
            if self.reply:
                _reply = Reply.get_one(str(self.reply), check_online=False)
                _reply.update_model({'$inc': {'reply_count': 1}})

            key = self.COMMENT_REPLY_IDS % ({'cid': str(self.comment)})
            # 列表为空时key对应的value是一个string
            try:
                if Redis.exists(key):
                    Redis.zadd(key, self.create_at, str(_id))
            except exceptions.ResponseError:
                Redis.delete(key)
        return _id

    def delete_model(self):
        ret = super(Reply, self).delete_model()
        if ret:
            # 更新评论回复数
            comment = Comment.get_one(str(self.comment), check_online=False)
            comment.update_model({'$inc': {'reply': -1}})
            # 更新回复的回复数
            if self.reply:
                _reply = Reply.get_one(str(self.reply), check_online=False)
                _reply.update_model({'$inc': {'reply_count': -1}})

            key = self.COMMENT_REPLY_IDS % ({'cid': str(self.comment)})
            try:
                Redis.zrem(key, str(self._id))
            except exceptions.ResponseError:
                Redis.delete(key)
        return ret

    @classmethod
    def init(cls):
        doc = super(Reply, cls).init()
        doc.reply_count = 0
        return cls(doc)

    @classmethod
    def delete_comment_replies(cls, cid):
        ret = cls.collection.delete_many({'comment': ObjectId(cid)})
        return ret.deleted_count

    @classmethod
    @util.cached_zset(lambda cls, cid: cls.COMMENT_REPLY_IDS % ({'cid': cid}),
                      snowslide=True)
    def _load_comment_reply_ids(cls, cid):
        replies = list(cls.collection.find(
            {
                'comment': ObjectId(cid)
            },
            {'_id': 1, 'create_at': 1}
        ).sort("create_at", pymongo.DESCENDING))
        ret = list()
        for c in replies:
            if 'create_at' in c:
                ret.extend([c['create_at'], str(c['_id'])])
        return tuple(ret)

    @classmethod
    def comment_reply_ids(cls, cid, page=None, pagesize=None, maxs=None):
        """获取评论的回复id
        """
        key = cls.COMMENT_REPLY_IDS % ({'cid': cid})
        if not Redis.exists(key):
            cls._load_comment_reply_ids(cid)
        try:
            if maxs:
                ids = Redis.zrangebyscore(key, '(%.6f' % (maxs), '+inf', start=0, num=pagesize)
            else:
                start = (page - 1) * pagesize
                stop = start + pagesize - 1
                ids = Redis.zrange(key, start, stop)
        except exceptions.ResponseError:
            # 列表为空时key对应的value是一个string
            ids = []
        return list(ids)
