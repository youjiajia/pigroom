# -*- coding: utf8 -*-
from bson.objectid import ObjectId
from flask import request
from wanx.base.spam import Spam
from wanx.base.xredis import Redis
from wanx.models.comment import Comment, UserLikeComment, Reply
from wanx.models.msg import Message
from wanx.models.video import Video
from wanx.models.task import UserTask, COMMENT_VIDEO
from wanx.models.gift import UserGiftLog
from wanx.models.activity import ActivityVideo, ActivityConfig
from wanx import app
from wanx.base import util, error, const

import time


# TODO: being delete opt in url
@app.route('/user/opt/submit-comment', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def create_comment():
    """创建评论 (GET|POST&LOGIN)

    :uri: /user/opt/submit-comment
    :param video_id: 被评论视频id
    :param content: 评论内容
    :returns: {'comment': object}
    """
    user = request.authed_user
    params = request.values
    vid = params.get('video_id', None)
    content = params.get('content', None)
    if not vid or not content:
        return error.InvalidArguments

    if not Video.get_one(vid):
        return error.VideoNotExist

    # 敏感词检查
    if Spam.filter_words(content, 'comment'):
        return error.InvalidContent
    comment = Comment.init()
    comment.author = ObjectId(str(user._id))
    comment.content = content
    comment.video = ObjectId(vid)
    cid = comment.create_model()
    if cid:
        # 发送评论消息
        Message.send_video_msg(str(user._id), str(vid), 'comment')

    # 任务检查
    if user:
        UserTask.check_user_tasks(str(user._id), COMMENT_VIDEO, 1)

        # 更新活动评论数
        avideos = ActivityVideo.get_activity_video(vid=vid)
        for avideo in avideos:
            ts = time.time()
            aconfig = ActivityConfig.get_one(str(avideo['activity_id']), check_online=False)
            if aconfig and aconfig.status == const.ACTIVITY_BEGIN \
                    and (aconfig.begin_at < ts and aconfig.end_at > ts):
                avideo = ActivityVideo.get_one(avideo['_id'], check_online=False)
                avideo.update_model({'$inc': {'comment_count': 1}})

    return Comment.get_one(str(cid)).format()


# TODO: being delete opt in url
@app.route('/user/opt/delete-comment', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def delete_comment():
    """删除评论 (GET|POST&LOGIN)

    :uri: /user/opt/delete-comment
    :param comment_id: 评论id
    :returns: {}
    """
    user = request.authed_user
    params = request.values
    cid = params.get('comment_id', None)
    comment = Comment.get_one(cid)
    if not comment:
        return error.CommentNotExist
    if str(comment.author) != str(user._id):
        return error.AuthFailed
    comment.delete_model()
    # 更新活动评论数
    avideos = ActivityVideo.get_activity_video(vid=str(comment.video))
    for avideo in avideos:
        ts = time.time()
        aconfig = ActivityConfig.get_one(str(avideo['activity_id']), check_online=False)
        if aconfig and aconfig.status == const.ACTIVITY_BEGIN \
                and (aconfig.begin_at < ts and aconfig.end_at > ts):
            avideo = ActivityVideo.get_one(avideo['_id'], check_online=False)
            avideo.update_model({'$inc': {'comment_count': -1}})
    return {}


# TODO: being delete opt in url
@app.route('/user/opt/like-comment', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def like_comment():
    """赞评论 (GET|POST&LOGIN)

    :uri: /user/opt/like-comment
    :param comment_id: 被赞评论id
    :returns: {}
    """
    user = request.authed_user
    cid = request.values.get('comment_id', None)
    comment = Comment.get_one(cid)
    if not comment:
        return error.CommentNotExist

    ulc = UserLikeComment.get_by_ship(str(user._id), cid)
    if not ulc:
        key = 'lock:like_comment:%s:%s' % (str(user._id), cid)
        with util.Lockit(Redis, key) as locked:
            if locked:
                return error.LikeCommentFailed
            ulc = UserLikeComment.init()
            ulc.source = ObjectId(str(user._id))
            ulc.target = ObjectId(cid)
            ulc.create_model()
            # 发送点赞消息
            Message.send_comment_msg(str(user._id), str(cid), 'like')
    return {}


@app.route('/user/opt/unlike-comment', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def unlike_comment():
    """取消赞评论 (GET|POST&LOGIN)

    :uri: /user/opt/unlike-comment
    :param comment_id: 被赞评论id
    :returns: {}
    """
    user = request.authed_user
    cid = request.values.get('comment_id', None)
    comment = Comment.get_one(cid)
    if not comment:
        return error.CommentNotExist

    key = 'lock:unlike_comment:%s:%s' % (str(user._id), cid)
    with util.Lockit(Redis, key) as locked:
        if locked:
            return error.LikeCommentFailed('取消赞评论失败')
        ulc = UserLikeComment.get_by_ship(str(user._id), cid)
        ulc.delete_model() if ulc else None
    return {}


@app.route('/videos/<string:vid>/comments/', methods=['GET'])
@util.jsonapi()
def video_comments(vid):
    """获取视频评论 (GET)

    :uri: /videos/<string:vid>/comments/
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
    next_maxs = None
    while len(comments) < pagesize:
        cids = Comment.video_comment_ids(vid, page, pagesize, maxs)
        comments.extend([c.format() for c in Comment.get_list(cids)])

        # 如果按照maxs分页, 不足pagesize个记录则继续查询
        if maxs is not None:
            obj = Comment.get_one(cids[-1], check_online=False) if cids else None
            next_maxs = obj.create_at if obj else 1000
            if len(cids) < pagesize:
                break
        else:
            break

    end_page = len(cids) < pagesize

    if maxs is not None:
        gift_logs = UserGiftLog.get_video_gifts(vid, maxs, pagesize)

        comments.extend([gl.format() for gl in gift_logs])
        comments = sorted(comments, key=lambda x: x['create_at'], reverse=True)[:pagesize]
        next_maxs = comments[-1]['create_at'] if comments else 1000
        end_page = (len(cids) + len(gift_logs)) < pagesize

    # 评论增加3个回复
    for comment in comments:
        if 'comment_id' in comment:
            rids = Reply.comment_reply_ids(comment['comment_id'], 1, 4, 0)
            comment['replies'] = [r.format() for r in Reply.get_list(rids)]
            comment['type'] = 'comment'
        else:
            comment['type'] = 'gift'

    return {'comments': comments, 'end_page': end_page, 'maxs': next_maxs}


@app.route('/replies/create', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def create_reply():
    """创建评论的回复 (GET|POST&LOGIN)

    :uri: /replies/create
    :param comment_id: 评论id(可选)
    :param reply_id: 被用户回复的评论回复id(可选)
    :param content: 回复内容
    :returns: {'reply': object}
    """
    user = request.authed_user
    params = request.values
    cid = params.get('comment_id', None)
    reply_id = params.get('reply_id', None)
    content = params.get('content', None)
    if not content or (not cid and not reply_id):
        return error.InvalidArguments

    comment = Comment.get_one(cid) if cid else None
    if cid and not comment:
        return error.CommentNotExist

    reply = Reply.get_one(reply_id) if reply_id else None
    if reply_id and not reply:
        return error.ReplyNotExist

    # 敏感词检查
    if Spam.filter_words(content, 'comment'):
        return error.InvalidContent

    new_reply = Reply.init()
    new_reply.owner = user._id
    new_reply.reply = reply._id if reply else None
    new_reply.comment = reply.comment if reply else comment._id
    new_reply.content = content
    rid = new_reply.create_model()
    if rid:
        # 发送消息
        if reply:
            Message.send_reply_msg(str(user._id), str(reply._id), 'reply')
        else:
            Message.send_comment_msg(str(user._id), str(cid), 'reply')
    return {'reply': Reply.get_one(str(rid)).format() if rid else None}


@app.route('/replies/<string:rid>/delete', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def delete_reply(rid):
    """删除回复 (GET|POST&LOGIN)

    :uri: /replies/<string:rid>/delete
    :returns: {}
    """
    user = request.authed_user
    reply = Reply.get_one(rid)
    if not reply:
        return error.ReplyNotExist

    if str(reply.owner) != str(user._id):
        return error.AuthFailed
    reply.delete_model()
    return {}


@app.route('/comment/<string:cid>/replies', methods=['GET'])
@util.jsonapi()
def comment_replies(cid):
    """获取评论所有回复 (GET&LOGIN)

    :uri: /comment/<string:cid>/replies
    :param maxs: 最后时间, 0代表当前时间, 无此参数按page来分页
    :param page: 页码(数据可能有重复, 建议按照maxs分页)
    :param nbr: 每页数量
    :returns: {'replies': list, 'end_page': bool, 'maxs': timestamp}
    """
    params = request.values
    maxs = params.get('maxs', None)
    maxs = 1000 if maxs is not None and int(float(maxs)) == 0 else maxs and float(maxs)
    page = int(params.get('page', 1))
    pagesize = int(params.get('nbr', 10))

    comment = Comment.get_one(cid)
    if not comment:
        return error.CommentNotExist

    replies = list()
    rids = list()
    while len(replies) < pagesize:
        rids = Reply.comment_reply_ids(cid, page, pagesize, maxs)
        replies.extend([r.format() for r in Reply.get_list(rids)])

        # 如果按照maxs分页, 不足pagesize个记录则继续查询
        if maxs is not None:
            obj = Reply.get_one(rids[-1], check_online=False) if rids else None
            maxs = obj.create_at if obj else 1000000000000
            if len(rids) < pagesize:
                break
        else:
            break

    return {'replies': replies, 'end_page': len(rids) != pagesize, 'maxs': maxs}
