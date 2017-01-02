# -*- coding: utf8 -*-
from bson.objectid import ObjectId
from wanx import app
from wanx.base.spam import Spam
from wanx.base.xmongo import DB
from wanx.base.xredis import MRedis
from wanx.models import Document
from wanx.models.video import Video
from wanx.models.comment import Comment, Reply
from wanx.models.user import User
from wanx.base import const
from wanx.models.user import UserGroup, Group

import json
import pymongo


class Message(Document):
    """评论&点赞消息
    owner: 消息所有者
    ctype: 评论点赞对象类型(video:视频, comment:评论, reply:评论回复)
    obj_id: 对象ID
    action: 动作(like:点赞, comment:评论, reply:回复, gift:送礼)
    operator: 操作用户
    create_at: 创建时间
    """

    collection = DB.messages

    USER_MSG_IDS = 'msg:user:%(uid)s'

    def format(self):
        from wanx.models.user import User
        from wanx.models.comment import Comment
        from wanx.models.video import Video
        operator = User.get_one(str(self.operator), check_online=False)
        if self.ctype == 'comment':
            obj = Comment.get_one(str(self.obj_id), check_online=False)
            obj = obj and obj.format()
        elif self.ctype == 'video':
            obj = Video.get_one(str(self.obj_id), check_online=False)
            obj = obj and obj.format()
        elif self.ctype == 'reply':
            obj = Reply.get_one(str(self.obj_id), check_online=False)
            comment_id = obj and str(obj.comment)
            obj = obj and obj.format()
            if obj:
                comment = Comment.get_one(comment_id, check_online=False)
                obj['video_id'] = comment.video and str(comment.video)
        else:
            obj = None
        data = {
            'msg_id': str(self._id),
            'ctype': self.ctype,
            'obj': obj,
            'action': self.action,
            'operator': operator and operator.format(),
            'create_at': self.create_at
        }
        return data

    @classmethod
    def send_video_msg(cls, operator_id, obj_id, action='like'):
        owner_id = str(Video.get_one(obj_id).author)
        obj = cls.init()
        obj.owner = ObjectId(owner_id)
        obj.ctype = 'video'
        obj.obj_id = ObjectId(obj_id)
        obj.action = action
        obj.operator = ObjectId(operator_id)
        msg_id = obj.create_model()
        # 发送消息到队列
        channel = User.USER_ASYNC_MSG % ({'uid': owner_id})
        msg = dict(obj_type='Message', obj_id=str(msg_id), count=1)
        MRedis.publish(channel, json.dumps(msg))

    @classmethod
    def send_comment_msg(cls, operator_id, obj_id, action='like'):
        owner_id = str(Comment.get_one(obj_id).author)
        obj = cls.init()
        obj.owner = ObjectId(owner_id)
        obj.ctype = 'comment'
        obj.obj_id = ObjectId(obj_id)
        obj.action = action
        obj.operator = ObjectId(operator_id)
        msg_id = obj.create_model()
        # 发送消息到队列
        channel = User.USER_ASYNC_MSG % ({'uid': owner_id})
        msg = dict(obj_type='Message', obj_id=str(msg_id), count=1)
        MRedis.publish(channel, json.dumps(msg))

    @classmethod
    def send_reply_msg(cls, operator_id, obj_id, action='reply'):
        owner_id = str(Reply.get_one(obj_id).owner)
        obj = cls.init()
        obj.owner = ObjectId(owner_id)
        obj.ctype = 'reply'
        obj.obj_id = ObjectId(obj_id)
        obj.action = action
        obj.operator = ObjectId(operator_id)
        msg_id = obj.create_model()
        # 发送消息到队列
        channel = User.USER_ASYNC_MSG % ({'uid': owner_id})
        msg = dict(obj_type='Message', obj_id=str(msg_id), count=1)
        MRedis.publish(channel, json.dumps(msg))

    @classmethod
    def send_gift_msg(cls, operator_id, obj_id, action='gift'):
        owner_id = str(Video.get_one(obj_id).author)
        obj = cls.init()
        obj.owner = ObjectId(owner_id)
        obj.ctype = 'video'
        obj.obj_id = ObjectId(obj_id)
        obj.action = action
        obj.operator = ObjectId(operator_id)
        msg_id = obj.create_model()
        # 发送消息到队列
        channel = User.USER_ASYNC_MSG % ({'uid': owner_id})
        msg = dict(obj_type='Message', obj_id=str(msg_id), count=1)
        MRedis.publish(channel, json.dumps(msg))

    @classmethod
    def user_new_messages(cls, uid):
        msgs = list(cls.collection.find(
            {
                'owner': ObjectId(uid)
            }
        ).sort("update_at", pymongo.DESCENDING))
        msgs = [cls(msg) for msg in msgs]
        return msgs

    @classmethod
    def delete_user_messages(cls, uid, ts):
        ret = cls.collection.delete_many(
            {
                'owner': ObjectId(uid),
                'create_at': {'$lte': ts}
            }
        )
        return ret.deleted_count


class SysMessage(Document):
    """系统消息
    title: 标题
    image: 图片
    content: 正文
    link: 链接
    create_at: 创建时间
    """
    collection = DB.sys_messages

    def format(self):
        data = {
            'msg_id': str(self._id),
            'title': self.title,
            'image': "%s%s" % (app.config.get("MEDIA_URL"), self.image) if self.image else None,
            'content': self.content,
            'link': self.link,
            'create_at': self.begin_at or self.create_at,
        }
        return data

    @classmethod
    def sys_new_messages(cls, ts, cts):
        """
        获取系统未读消息
        :param ts: 用户上次未读消息时间，用于过滤生效时间早于ts的消息
        :param cts: 当前时间，用于判断消息是否在有效期
        :return:
        """
        msgs = list(cls.collection.find(
            {
                'begin_at': {'$gte': ts or 0, '$lte': cts},
                'expire_at': {'$gte': cts},
                'owner': {'$exists': False}
            }
        ).sort("begin_at", pymongo.DESCENDING))
        msgs = [cls(msg) for msg in msgs]
        return msgs

    @classmethod
    def sys_user_messages(cls, ts, uid):
        msgs = list(cls.collection.find(
            {
                'create_at': {'$gt': ts},
                'owner': ObjectId(uid)
            }
        ).sort("create_at", pymongo.DESCENDING))
        msgs = [cls(msg) for msg in msgs]
        return msgs

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


class Letter(Document):
    """私信
    owner: 私信所有者
    sender: 私信发送者
    content: 内容
    create_at: 创建时间
    """
    collection = DB.letters

    def format(self):
        from wanx.models.user import User
        sender = User.get_one(str(self.sender), check_online=False)
        data = {
            'msg_id': str(self._id),
            'sender': sender and sender.format(),
            'content': Spam.replace_words(self.content),
            'create_at': self.create_at
        }
        return data

    def create_model(self):
        _id = super(Letter, self).create_model()
        if _id:
            # 发送消息到队列
            channel = User.USER_ASYNC_MSG % ({'uid': str(self.owner)})
            letter = dict(obj_type='Letter', obj_id=str(_id), count=1)
            MRedis.publish(channel, json.dumps(letter))

        return _id

    @classmethod
    def user_new_letters(cls, uid, sender):
        letters = list(cls.collection.find(
            {
                'owner': ObjectId(uid),
                'sender': ObjectId(sender)
            }
        ).sort("create_at", pymongo.DESCENDING))
        letters = [cls(letter) for letter in letters]
        return letters

    @classmethod
    def new_letter_count(cls, uid):
        users = cls.collection.aggregate([
            {'$match': {'owner': ObjectId(uid)}},
            {
                '$group':
                    {
                        '_id': '$sender',
                        'last_id': {'$last': '$_id'},
                        'count': {'$sum': 1}
                    }
            }
        ])
        return list(users) if users else []

    @classmethod
    def delete_user_letters(cls, uid, sid, ts):
        ret = cls.collection.delete_many(
            {
                'owner': ObjectId(uid),
                'sender': ObjectId(sid),
                'create_at': {'$lte': ts}
            }
        )
        return ret.deleted_count


class Suggestion(Document):
    """意见反馈
    contact: 联系方式
    content: 反馈内容
    user: 发送人
    """
    collection = DB.suggestions
