# -*- coding: utf8 -*-
from bson.objectid import ObjectId
from flask import request, Blueprint
from wanx.base.spam import Spam
from wanx.base.xredis import Redis
from wanx.models.activity import ActivityComment, UserLikeActivityComment, ActivityConfig
from wanx.base import util, error

import time

comment = Blueprint("comment", __name__, url_prefix="/activity")


@comment.route('/user/submit-comment', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def activity_create_comment():
    """创建评论 (GET|POST&LOGIN)

    :uri: /activity/user/submit-comment
    :param activity_id: 被评论活动id
    :param content: 评论内容
    :returns: {'comment': object}
    """
    user = request.authed_user
    params = request.values
    aid = params.get('activity_id', None)
    content = params.get('content', None)
    if not aid or not content:
        return error.InvalidArguments

    if not ActivityConfig.get_one(aid, check_online=False):
        return error.ActivityNotExist

    # 敏感词检查
    if Spam.filter_words(content, 'comment'):
        return error.InvalidContent

    comment = ActivityComment.init()
    comment.activity = ObjectId(aid)
    comment.author = ObjectId(str(user._id))
    comment.content = content
    cid = comment.create_model()
    return ActivityComment.get_one(str(cid)).format()


@comment.route('/user/delete-comment', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def activity_delete_comment():
    """删除评论 (GET|POST&LOGIN)

    :uri: /activity/user/delete-comment
    :param comment_id: 评论id
    :returns: {}
    """
    user = request.authed_user
    params = request.values
    cid = params.get('comment_id', None)
    comment = ActivityComment.get_one(cid)
    if not comment:
        return error.CommentNotExist
    if str(comment.author) != str(user._id):
        return error.AuthFailed
    comment.delete_model()
    return {}


@comment.route('/user/like-comment', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def activity_like_comment():
    """赞评论 (GET|POST&LOGIN)

    :uri: /activity/user/like-comment
    :param comment_id: 被赞评论id
    :returns: {}
    """
    user = request.authed_user
    cid = request.values.get('comment_id', None)
    comment = ActivityComment.get_one(cid)
    if not comment:
        return error.CommentNotExist

    ulc = UserLikeActivityComment.get_by_ship(str(user._id), cid)
    if not ulc:
        key = 'lock:activity:like_comment:%s:%s' % (str(user._id), cid)
        with util.Lockit(Redis, key) as locked:
            if locked:
                return error.LikeCommentFailed
            ulc = UserLikeActivityComment.init()
            ulc.source = ObjectId(str(user._id))
            ulc.target = ObjectId(cid)
            ulc.create_model()
    return {}


@comment.route('/user/unlike-comment', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def activity_unlike_comment():
    """取消赞评论 (GET|POST&LOGIN)

    :uri: /activity/user/unlike-comment
    :param comment_id: 被赞评论id
    :returns: {}
    """
    user = request.authed_user
    cid = request.values.get('comment_id', None)
    comment = ActivityComment.get_one(cid)
    if not comment:
        return error.CommentNotExist

    key = 'lock:activity:unlike_comment:%s:%s' % (str(user._id), cid)
    with util.Lockit(Redis, key) as locked:
        if locked:
            return error.LikeCommentFailed('取消赞评论失败')
        ulc = UserLikeActivityComment.get_by_ship(str(user._id), cid)
        ulc.delete_model() if ulc else None
    return {}


@comment.route('/<string:aid>/comments', methods=['GET'])
@util.jsonapi()
def activity_comments(aid):
    """获取活动评论 (GET)

    :uri: /activity/<string:aid>/comments/
    :param maxs: 最后时间, 0代表当前时间, 无此参数按page来分页
    :param page: 页码(数据可能有重复, 建议按照maxs分页)
    :param nbr: 每页数量
    :returns: {'comments': list, 'end_page': bool, 'maxs': timestamp}
    """
    params = request.values
    maxs = params.get('maxs', None)
    maxs = time.time() if maxs is not None and int(float(maxs)) == 0 else maxs and float(maxs)
    page = int(params.get('page', 1))
    pagesize = int(params.get('nbr', 10))

    comments = list()
    cids = list()
    while len(comments) < pagesize:
        cids = ActivityComment.activity_comment_ids(aid, page, pagesize, maxs)
        comments.extend([c.format() for c in ActivityComment.get_list(cids)])

        # 如果按照maxs分页, 不足pagesize个记录则继续查询
        if maxs is not None:
            obj = ActivityComment.get_one(cids[-1], check_online=False) if cids else None
            maxs = obj.create_at if obj else 1000
            if len(cids) < pagesize:
                break
        else:
            break

    return {'comments': comments, 'end_page': len(cids) != pagesize, 'maxs': maxs}
