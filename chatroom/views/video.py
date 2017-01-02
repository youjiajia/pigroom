# -*- coding: utf8 -*-
from bson.objectid import ObjectId
from flask import request, redirect, jsonify
from wanx.base.spam import Spam
from wanx.base.xredis import Redis
from wanx.models.home import Share
from wanx.models.video import (Video, UserFaverVideo, UserLikeVideo, ReportVideo,
                               VideoCategory, CategoryVideo, VideoTopic, TopicVideo)
from wanx.models.game import UserSubGame, Game, CategoryGame
from wanx.models.user import FriendShip
from wanx.models.msg import Message
from wanx.models.comment import Comment
from wanx.models.user import User
from wanx.models.task import UserTask, CREATE_VIDEO, PLAY_VIDEO
from wanx.models.activity import ActivityConfig, ActivityVideo
from wanx import app
from wanx.base import util, error, const

import time
import hashlib

from wanx.platforms import Xlive


@app.route('/migu/videos/<string:vid>')
@app.route('/videos/<string:vid>', methods=['GET'])
@util.jsonapi()
def get_video(vid):
    """获取视频详细信息 (GET)

    :uri: /videos/<string:vid>
    :uri migu: /migu/videos/<string:vid>
    :returns: object
    """
    video = Video.get_one(vid, check_online=False)
    if not video:
        return error.VideoNotExist

    return video.format()


@app.route('/videos/new-video', methods=('POST',))
@util.jsonapi(login_required=True)
def create_video():
    """创建视频 (POST&LOGIN)

    :uri: /videos/new-video
    :param game_id: 视频所属游戏id
    :param title: 视频标题
    :param duration: 视频时长
    :param ratio: 视频尺寸
    :returns: object
    """
    user = request.authed_user
    gid = request.values['game_id']
    game = Game.get_one(gid)
    if not game:
        return error.GameNotExist
    video = Video.init()
    video.author = ObjectId(user._id)
    video.game = ObjectId(gid)
    video.title = request.values['title']
    # 敏感词检查
    if Spam.filter_words(video.title, 'video'):
        return error.InvalidContent
    try:
        duration = int(request.values['duration'])
    except:
        return error.InvalidArguments

    video.duration = duration
    video.ratio = request.values['ratio']
    # 设置为文件上传状态, 文件上传成功之后更改为上线状态
    video.status = const.UPLOADING
    vid = video.create_model()

    # 任务检查
    if user:
        UserTask.check_user_tasks(str(user._id), CREATE_VIDEO, 1)

    return Video.get_one(vid, check_online=False).format()


@app.route('/videos/<string:vid>/modify-video', methods=('POST',))
@util.jsonapi(login_required=True)
def modify_video(vid):
    """更新视频信息接口 (POST&LOGIN)

    :uri: /videos/<string:vid>/modify-video
    :param title: 视频标题
    :return: {'video': <Video>object}
    """
    user = request.authed_user
    title = request.values.get('title')
    if not title:
        return error.InvalidArguments

    video = Video.get_one(vid, check_online=False)
    if not video or video.author != user._id:
        return error.VideoNotExist("视频不存在或视频不属于此用户")

    data = {'title': title}
    video = video.update_model({"$set": data})
    return {'video': video.format()}


@app.route('/videos/<string:vid>/update-video', methods=('POST',))
@util.jsonapi(verify=False)
def update_video(vid):
    """修改视频--文件上传走第三方，供第三方进行回调 (POST)

    :uri: /videos/<string:vid>/update-video
    :param cover: 背景相对路径
    :param url: 视频相对路径
    :param upload_sig: 验证串
    :return: {'url': string}
    """
    cover = request.values.get('cover')
    url = request.values.get('url')
    valid_sig = request.values.get('upload_sig')
    md5 = hashlib.md5(vid)
    secret = '&%s' % ('29eb78ff3c8f20fe')
    md5.update(secret)
    if valid_sig != md5.hexdigest() or not cover or not url:
        return error.InvalidArguments

    video = Video.get_one(vid, check_online=False)
    if not video:
        return error.VideoNotExist

    data = {'cover': cover, 'url': url, 'status': const.ONLINE}
    video = video.update_model({"$set": data})
    return {'video': video.format()}


@app.route('/videos/<string:vid>/delete', methods=('POST',))
@util.jsonapi(login_required=True)
def delete_video(vid):
    """删除视频 (POST&LOGIN)

    :uri: /videos/<string:vid>/delete
    :returns: {}
    """
    user = request.authed_user
    video = Video.get_one(vid, check_online=False)
    if not video:
        return error.VideoNotExist
    if str(user._id) != str(video.author):
        return error.AuthFailed
    video.delete_model()
    return {}


@app.route('/videos/<string:vid>/play', methods=['GET'])
def play_video(vid):
    """播放视频 (GET)

    :uri: /videos/<string:vid>/play
    :returns: redirect(real_url)
    """
    ut = request.values.get("ut", None)
    uid = User.uid_from_token(ut)

    start = int(time.time() * 1000)
    video = Video.get_one(vid)
    if not video:
        result = {
            'status': error.VideoNotExist.errno,
            'errmsg': error.VideoNotExist.errmsg,
            'data': {},
            'time': int(time.time() * 1000) - start,
        }
        return jsonify(result)
    video.update_model({'$inc': {'vv': 1}})
    # 观看视频任务检查
    if uid:
        UserTask.check_user_tasks(uid, PLAY_VIDEO, 1)

    # 更新活动播放量
    avideos = ActivityVideo.get_activity_video(vid=vid)
    for avideo in avideos:
        ts = time.time()
        aconfig = ActivityConfig.get_one(str(avideo['activity_id']), check_online=False)
        if aconfig and aconfig.status == const.ACTIVITY_BEGIN \
                and (aconfig.begin_at < ts and aconfig.end_at > ts):
            avideo = ActivityVideo.get_one(avideo['_id'], check_online=False)
            avideo.update_model({'$inc': {'vv': 1}})

    return redirect(video.real_url())


# TODO: being delete opt in url
@app.route('/user/opt/favorite-video', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def favorite_video():
    """收藏视频 (GET|POST&LOGIN)

    :uri: /user/opt/favorite-video
    :param video_id: 被收藏视频id
    :returns: {}
    """
    user = request.authed_user
    vid = request.values.get('video_id', None)
    video = Video.get_one(vid)
    if not video:
        return error.VideoNotExist
    ufv = UserFaverVideo.get_by_ship(str(user._id), vid)
    if not ufv:
        key = 'lock:favor_video:%s:%s' % (str(user._id), vid)
        with util.Lockit(Redis, key) as locked:
            if locked:
                return error.FavorVideoFailed
            ufv = UserFaverVideo.init()
            ufv.source = ObjectId(str(user._id))
            ufv.target = ObjectId(vid)
            ufv.create_model()
    return {}


# TODO: being delete opt in url
@app.route('/user/opt/unfavorite-video', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def unfavorite_video():
    """取消收藏视频 (GET|POST&LOGIN)

    :uri: /user/opt/unfavorite-video
    :param video_id: 收藏视频id
    :returns: {}
    """
    user = request.authed_user
    vid = request.values.get('video_id', None)
    video = Video.get_one(vid)
    if not video:
        return error.VideoNotExist

    key = 'lock:unfavor_video:%s:%s' % (str(user._id), vid)
    with util.Lockit(Redis, key) as locked:
        if locked:
            return error.FavorVideoFailed('取消收藏失败')
        ufv = UserFaverVideo.get_by_ship(str(user._id), vid)
        ufv.delete_model() if ufv else None
    return {}


@app.route('/user/opt/like-video', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def like_video():
    """赞视频 (GET|POST&LOGIN)

    :uri: /user/opt/like-video
    :param video_id: 被赞视频id
    :returns: {}
    """
    user = request.authed_user
    vid = request.values.get('video_id', None)
    video = Video.get_one(vid)
    if not video:
        return error.VideoNotExist

    ulv = UserLikeVideo.get_by_ship(str(user._id), vid)
    if not ulv:
        key = 'lock:like_video:%s:%s' % (str(user._id), vid)
        with util.Lockit(Redis, key) as locked:
            if locked:
                return error.LikeVideoFailed
            ulv = UserLikeVideo.init()
            ulv.source = ObjectId(str(user._id))
            ulv.target = ObjectId(vid)
            _id = ulv.create_model()
            if _id:
                # 发送点赞消息
                Message.send_video_msg(str(user._id), str(vid), 'like')
                # 更新活动点赞数
                avideos = ActivityVideo.get_activity_video(vid=vid)
                for avideo in avideos:
                    ts = time.time()
                    aconfig = ActivityConfig.get_one(str(avideo['activity_id']), check_online=False)
                    if aconfig and aconfig.status == const.ACTIVITY_BEGIN \
                            and (aconfig.begin_at < ts and aconfig.end_at > ts):
                        avideo = ActivityVideo.get_one(avideo['_id'], check_online=False)
                        avideo.update_model({'$inc': {'like_count': 1}})

    return {}


@app.route('/user/opt/unlike-video', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def unlike_video():
    """取消赞视频 (GET|POST&LOGIN)

    :uri: /user/opt/like-video
    :param video_id: 被赞视频id
    :returns: {}
    """
    user = request.authed_user
    vid = request.values.get('video_id', None)
    video = Video.get_one(vid)
    if not video:
        return error.VideoNotExist

    key = 'lock:unlike_video:%s:%s' % (str(user._id), vid)
    with util.Lockit(Redis, key) as locked:
        if locked:
            return error.LikeVideoFailed('取消赞失败')
        ulv = UserLikeVideo.get_by_ship(str(user._id), vid)
        ulv.delete_model() if ulv else None
        # 更新活动点赞数
        avideos = ActivityVideo.get_activity_video(vid=vid)
        for avideo in avideos:
            ts = time.time()
            aconfig = ActivityConfig.get_one(str(avideo['activity_id']), check_online=False)
            if aconfig and aconfig.status == const.ACTIVITY_BEGIN \
                    and (aconfig.begin_at < ts and aconfig.end_at > ts):
                avideo = ActivityVideo.get_one(avideo['_id'], check_online=False)
                avideo.update_model({'$inc': {'like_count': -1}})
    return {}


@app.route('/user/report-video', methods=['POST'])
@util.jsonapi()
def report_video():
    """举报视频 (POST)

    :uri: /user/report-video
    :param video_id: 被举报视频id
    :param type: 举报原因
    :param content: 举报内容
    :param source: 举报来源，0：来自视频，1：来自直播
    :returns: {}
    """
    params = request.values
    vid = params.get('video_id', None)
    type = int(params.get('type', 0))
    content = params.get('content', None)
    source = int(params.get('source', 0))

    if not vid or not type or source not in [0, 1]:
        return error.InvalidArguments

    if source == 0:
        video = Video.get_one(vid)
        if not video:
            return error.VideoNotExist
        uid = video.author
    else:
        live = Xlive.get_live(vid)
        if not live:
            return error.LiveError('直播不存在')
        uid = live.user_id

    key = 'lock:reported_videos:latest:%s' % (vid)
    with util.Lockit(Redis, key) as locked:
        if locked:
            return error.ReportVideoFailed('举报视频失败，请稍后再试')
        rv = ReportVideo.init()
        rv.uid = uid
        rv.vid = vid
        rv.type = type
        rv.content = content if content else ''
        rv.source = source
        rv.create_model()

        Redis.delete("reported_videos:latest")

    return {}


@app.route('/videos/current/', methods=['GET'])
@util.jsonapi()
def latest_video():
    """获取最新视频 (GET)

    :uri: /videos/current/
    :param maxs: 最后时间, 0代表当前时间, 无此参数按page来分页
    :param page: 页码
    :param nbr: 每页数量
    :returns: {'videos': list, 'end_page': bool, 'maxs': timestamp}
    """
    params = request.values
    maxs = params.get('maxs', None)
    maxs = time.time() if maxs is not None and int(float(maxs)) == 0 else maxs and float(maxs)
    page = int(params.get('page', 1))
    pagesize = int(params.get('nbr', 10))

    videos = list()
    vids = list()
    while len(videos) < pagesize:
        vids = Video.latest_video_ids(page, pagesize, maxs)
        ex_fields = ['is_favored', 'author__is_followed', 'game__subscribed']
        videos.extend([v.format(exclude_fields=ex_fields) for v in Video.get_list(vids)])

        # 如果按照maxs分页, 不足pagesize个记录则继续查询
        if maxs is not None:
            obj = Video.get_one(vids[-1], check_online=False) if vids else None
            maxs = obj.create_at if obj else 1000
            if len(vids) < pagesize:
                break
        else:
            break

    return {'videos': videos, 'end_page': len(vids) != pagesize, 'maxs': maxs}


@app.route('/videos/elite/', methods=['GET'])
@util.jsonapi()
def elite_video():
    """获取精选视频 (GET)

    :uri: /videos/elite/
    :param maxs: 最后时间, 0代表当前时间, 无此参数按page来分页
    :param page: 页码(数据可能有重复, 建议按照maxs分页)
    :param nbr: 每页数量
    :returns: {'videos': list, 'end_page': bool, 'maxs': timestamp}
    """
    params = request.values
    maxs = params.get('maxs', None)
    maxs = time.time() if maxs is not None and int(float(maxs)) == 0 else maxs and float(maxs)
    page = int(params.get('page', 1))
    pagesize = int(params.get('nbr', 10))

    videos = list()
    vids = list()
    while len(videos) < pagesize:
        vids = Video.elite_video_ids(page, pagesize, maxs)
        ex_fields = ['is_favored', 'is_liked', 'author__is_followed', 'game__subscribed']
        videos.extend([v.format(exclude_fields=ex_fields) for v in Video.get_list(vids)])

        # 如果按照maxs分页, 不足pagesize个记录则继续查询
        if maxs is not None:
            obj = Video.get_one(vids[-1], check_online=False) if vids else None
            maxs = obj.release_time if obj else 1000
            if len(vids) < pagesize:
                break
        else:
            break

    return {'videos': videos, 'end_page': len(vids) != pagesize, 'maxs': maxs}


@app.route('/users/<string:uid>/favors', methods=['GET'])
@util.jsonapi()
def favor_videos(uid):
    """获取用户收藏的视频 (GET)

    :uri: /users/<string:uid>/favors
    :param maxs: 最后时间, 0代表当前时间, 无此参数按page来分页
    :param page: 页码(数据可能有重复, 建议按照maxs分页)
    :param nbr: 每页数量
    :returns: {'videos': list, 'end_page': bool, 'maxs': timestamp}
    """
    params = request.values
    maxs = params.get('maxs', None)
    maxs = time.time() if maxs is not None and int(float(maxs)) == 0 else maxs and float(maxs)
    page = int(params.get('page', 1))
    pagesize = int(params.get('nbr', 10))

    videos = list()
    vids = list()
    while len(videos) < pagesize:
        vids = UserFaverVideo.faver_video_ids(uid, page, pagesize, maxs)
        ex_fields = ['is_favored', 'is_liked', 'author__is_followed', 'game__subscribed']
        videos.extend([v.format(exclude_fields=ex_fields) for v in Video.get_list(vids)])

        # 如果按照maxs分页, 不足pagesize个记录则继续查询
        if maxs is not None:
            obj = UserFaverVideo.get_by_ship(uid, vids[-1]) if vids else None
            maxs = obj.create_at if obj else 1000
            if len(vids) < pagesize:
                break
        else:
            break

    return {'videos': videos, 'end_page': len(vids) != pagesize, 'maxs': maxs}


@app.route('/users/<string:uid>/subscriptions', methods=['GET'])
@util.jsonapi()
def sub_game_videos(uid):
    """获取用户已订阅游戏的视频 (GET)

    :uri: /users/<string:uid>/subscriptions
    :returns: {'videos': list}
    """
    gids = UserSubGame.sub_game_ids(uid)
    games = Game.get_list(gids)
    ret = []
    for game in games:
        vids = Video.game_video_ids(str(game._id), 1, 4, time.time())
        ex_fields = ['is_favored', 'is_liked', 'author__is_followed', 'game__subscribed']
        videos = [v.format(exclude_fields=ex_fields) for v in Video.get_list(vids)]
        ret.append({'game': game.format(), 'videos': videos})
    return {'videos': ret}


@app.route('/users/<string:uid>/videos', methods=['GET'])
@util.jsonapi()
def user_videos(uid):
    """获取用户创建的视频 (GET)

    :uri: /users/<string:uid>/videos
    :params game_id: 游戏id, 不传取用户所有游戏的视频
    :param maxs: 最后时间, 0代表当前时间, 无此参数按page来分页
    :param page: 页码(数据可能有重复, 建议按照maxs分页)
    :param nbr: 每页数量
    :returns: {'videos': list, 'end_page': bool, 'maxs': timestamp}
    """
    params = request.values
    maxs = params.get('maxs', None)
    maxs = time.time() if maxs is not None and int(float(maxs)) == 0 else maxs and float(maxs)
    page = int(params.get('page', 1))
    pagesize = int(params.get('nbr', 10))
    gid = params.get('game_id', None)
    if gid and not Game.get_one(gid):
        return error.GameNotExist

    videos = list()
    vids = list()
    while len(videos) < pagesize:
        if gid:
            vids = Video.user_game_video_ids(uid, gid, page, pagesize, maxs)
        else:
            vids = Video.user_video_ids(uid, page, pagesize, maxs)
        ex_fields = ['is_favored', 'is_liked', 'author__is_followed', 'game__subscribed']
        videos.extend([v.format(exclude_fields=ex_fields) for v in Video.get_list(vids)])

        # 如果按照maxs分页, 不足pagesize个记录则继续查询
        if maxs is not None:
            obj = Video.get_one(vids[-1], check_online=False) if vids else None
            maxs = obj.create_at if obj else 1000
            if len(vids) < pagesize:
                break
        else:
            break

    return {'videos': videos, 'end_page': len(vids) != pagesize, 'maxs': maxs}


@app.route('/users/<string:uid>/live_videos', methods=['GET'])
@util.jsonapi()
def user_live_videos(uid):
    """获取用户直播转录播的视频 (GET)

    :uri: /users/<string:uid>/live_videos
    :param maxs: 最后时间, 0代表当前时间, 无此参数按page来分页
    :param page: 页码(数据可能有重复, 建议按照maxs分页)
    :param nbr: 每页数量
    :returns: {'videos': list, 'end_page': bool, 'maxs': timestamp}
    """
    params = request.values
    maxs = params.get('maxs', None)
    maxs = time.time() if maxs is not None and int(float(maxs)) == 0 else maxs and float(maxs)
    page = int(params.get('page', 1))
    pagesize = int(params.get('nbr', 10))

    videos = list()
    vids = list()
    while len(videos) < pagesize:
        vids = Video.user_live_video_ids(uid, page, pagesize, maxs)
        ex_fields = ['is_favored', 'is_liked', 'author__is_followed', 'game__subscribed']
        videos.extend([v.format(exclude_fields=ex_fields) for v in Video.get_list(vids)])

        # 如果按照maxs分页, 不足pagesize个记录则继续查询
        if maxs is not None:
            obj = Video.get_one(vids[-1], check_online=False) if vids else None
            maxs = obj.create_at if obj else 1000
            if len(vids) < pagesize:
                break
        else:
            break

    return {'videos': videos, 'end_page': len(vids) != pagesize, 'maxs': maxs}


@app.route('/games/<string:gid>/videos', methods=['GET'])
@util.jsonapi()
def game_videos(gid):
    """获取游戏的视频 (GET)

    :uri: /games/<string:gid>/videos
    :param maxs: 最后时间, 0代表当前时间, 无此参数按page来分页
    :param page: 页码(数据可能有重复, 建议按照maxs分页)
    :param nbr: 每页数量
    :param orderby: 排序方式 ('create_at': 创建时间, 'vv':播放次数)
    :returns: {'videos': list, 'end_page': bool, 'maxs': timestamp}
    """
    params = request.values
    orderby = params.get('orderby', 'create_at')
    maxs = params.get('maxs', None)
    if orderby == 'vv':
        maxs = 10000000 if maxs is not None and int(maxs) == 0 else maxs and int(maxs)
    else:
        maxs = time.time() if maxs is not None and int(float(maxs)) == 0 else maxs and float(maxs)
    page = int(params.get('page', 1))
    pagesize = int(params.get('nbr', 10))

    videos = list()
    vids = list()
    while len(videos) < pagesize:
        if orderby == 'vv':
            vids = Video.game_hotvideo_ids(gid, page, pagesize, maxs)
        else:
            vids = Video.game_video_ids(gid, page, pagesize, maxs)
        ex_fields = ['is_favored', 'is_liked', 'author__is_followed', 'game__subscribed']
        videos.extend([v.format(exclude_fields=ex_fields) for v in Video.get_list(vids)])

        # 如果按照maxs分页, 不足pagesize个记录则继续查询
        if maxs is not None:
            obj = Video.get_one(vids[-1], check_online=False) if vids else None
            if orderby == 'vv':
                maxs = obj.vv if obj else -1
            else:
                maxs = obj.create_at if obj else 1000

            if len(vids) < pagesize:
                break
        else:
            break

    return {'videos': videos, 'end_page': len(vids) != pagesize, 'maxs': maxs}


@app.route('/games/<string:gid>/live_videos', methods=['GET'])
@util.jsonapi()
def game_live_videos(gid):
    """获取游戏的视频 (GET)

    :uri: /games/<string:gid>/live_videos
    :param maxs: 最后时间, 0代表当前时间, 无此参数按page来分页
    :param page: 页码(数据可能有重复, 建议按照maxs分页)
    :param nbr: 每页数量
    :returns: {'videos': list, 'end_page': bool, 'maxs': timestamp}
    """
    params = request.values
    maxs = params.get('maxs', None)
    maxs = time.time() if maxs is not None and int(float(maxs)) == 0 else maxs and float(maxs)
    page = int(params.get('page', 1))
    pagesize = int(params.get('nbr', 10))

    videos = list()
    vids = list()
    while len(videos) < pagesize:
        vids = Video.game_video_ids(gid, page, pagesize, maxs)
        ex_fields = ['is_favored', 'is_liked', 'author__is_followed', 'game__subscribed']
        live_videos = filter(lambda x: x.event_id, Video.get_list(vids))
        videos.extend([v.format(exclude_fields=ex_fields) for v in live_videos])

        # 如果按照maxs分页, 不足pagesize个记录则继续查询
        if maxs is not None:
            obj = Video.get_one(vids[-1], check_online=False) if vids else None
            maxs = obj.create_at if obj else 1000

            if len(vids) < pagesize:
                break
        else:
            break

    return {'videos': videos, 'end_page': len(vids) != pagesize, 'maxs': maxs}


@app.route('/games/<string:gid>/popular/videos', methods=['GET'])
@util.jsonapi()
def game_popular_videos(gid):
    """获取游戏人气视频 (GET)

    :uri: /games/<string:gid>/videos
    :param page: 页码
    :param nbr: 每页数量
    :returns: {'videos': list, 'end_page': bool}
    """
    params = request.values
    page = int(params.get('page', 1))
    pagesize = int(params.get('nbr', 10))

    videos = list()
    vids = Video.game_hotvideo_ids(gid, page, pagesize)
    ex_fields = ['is_favored', 'is_liked', 'author__is_followed', 'game__subscribed']
    videos.extend([v.format(exclude_fields=ex_fields) for v in Video.get_list(vids)])
    return {'videos': videos, 'end_page': len(vids) != pagesize}


@app.route('/users/<string:uid>/followings/videos', methods=['GET'])
@util.jsonapi(login_required=True)
def user_followings_videos(uid):
    """获取用户偶像的视频 (GET&LOGIN)

    :uri: /users/<string:uid>/followings/videos
    :param maxs: 最后时间, 0代表当前时间, 无此参数按page来分页
    :param page: 页码(数据可能有重复, 建议按照maxs分页)
    :param nbr: 每页数量
    :returns: {'videos': list, 'end_page': bool, 'maxs': timestamp}
    """
    params = request.values
    user = request.authed_user
    maxs = params.get('maxs', None)
    maxs = time.time() if maxs is not None and int(float(maxs)) == 0 else maxs and float(maxs)
    page = int(params.get('page', 1))
    pagesize = int(params.get('nbr', 10))
    gid = params.get('game_id', None)
    uids = FriendShip.following_ids(str(user._id))
    uids = [ObjectId(_uid) for _uid in uids]

    videos = list()
    vids = list()
    while len(videos) < pagesize:
        vids = Video.users_video_ids(uids, gid, page, pagesize, maxs)
        ex_fields = ['is_favored', 'author__is_followed', 'game__subscribed']
        videos.extend([v.format(exclude_fields=ex_fields) for v in Video.get_list(vids)])

        # 如果按照maxs分页, 不足pagesize个记录则继续查询
        if maxs is not None:
            obj = Video.get_one(vids[-1]) if vids else None
            maxs = obj.create_at if obj else 1000
            if len(vids) < pagesize:
                break
        else:
            break

    return {'videos': videos, 'end_page': len(vids) != pagesize, 'maxs': maxs}


@app.route('/migu/tags/<string:cid>/videos/')
@app.route('/tags/<string:cid>/videos', methods=['GET'])
@util.jsonapi()
def tags_videos(cid):
    """获取标签下所有视频 (GET)

    :uri: /tags/<string:tid>/videos
    :uri migu: /migu/tags/<string:tid>/videos/
    :param maxs: 最后时间, 0代表当前时间, 无此参数按page来分页
    :param page: 页码(数据可能有重复, 建议按照maxs分页)
    :param nbr: 每页数量
    :returns: {'videos': list, 'end_page': bool, 'maxs': timestamp}
    """
    params = request.values
    maxs = params.get('maxs', None)
    maxs = time.time() if maxs is not None and int(float(maxs)) == 0 else maxs and float(maxs)
    page = int(params.get('page', 1))
    pagesize = int(params.get('nbr', 10))
    gids = CategoryGame.category_game_ids(cid)
    gids = [ObjectId(_gid) for _gid in gids]

    videos = list()
    vids = list()
    while len(videos) < pagesize:
        vids = Video.games_video_ids(gids, page, pagesize, maxs)
        ex_fields = ['is_favored', 'is_liked', 'author__is_followed', 'game__subscribed']
        videos.extend([v.format(exclude_fields=ex_fields) for v in Video.get_list(vids)])

        # 如果按照maxs分页, 不足pagesize个记录则继续查询
        if maxs is not None:
            obj = Video.get_one(vids[-1], check_online=False) if vids else None
            maxs = obj.create_at if obj else 1000
            if len(vids) < pagesize:
                break
        else:
            break

    return {'videos': videos, 'end_page': len(vids) != pagesize, 'maxs': maxs}


@app.route("/share/video/<string:vid>", methods=("GET",))
@util.jsonapi()
def get_share_video(vid):
    """获取视频分享数据(GET)

    :uri: /share/video/<string:vid>
    :returns: {'video': object, 'hot_videos': list, 'comments': comments,
               'game_url': url, 'app_url': url}
    """
    video = Video.get_one(vid)
    if not video:
        return error.VideoNotExist

    cids = Comment.video_comment_ids(vid, 1, 10)
    comments = [c.format() for c in Comment.get_list(cids)]

    vids = Video.game_hotvideo_ids(str(video.game), 1, 10)
    videos = [v.format() for v in Video.get_list(vids)]

    video = video.format()

    _from = request.values.get('ywfrom', None)
    mgyxdt_url = 'http://g.10086.cn/s/clientd/?t=GH_JFDX'
    game_url = video['game']['url'] if _from != 'miguyouxidating' else mgyxdt_url

    app_url = "http://video.cmgame.com/userfiles/wapapp/mgyw.apk"
    app_url = app_url if _from != 'miguyouxidating' else '#'

    return dict(
        video=video,
        hot_videos=videos,
        comments=comments,
        game_url=game_url,
        app_url=app_url
    )


@app.route("/videos/event_id", methods=("GET",))
@util.jsonapi()
def get_video_id():
    """通过直播间id获取视频(GET)

    :uri: /videos/event_id
    :param: event_id: 直播间id
    :return: {'video': Object}
    """
    uid = request.authed_user and str(request.authed_user._id)
    eid = request.values.get('event_id', None)
    if not eid:
        return error.LiveError("直播间id不存在")

    vid = Video.get_video_by_event_id(eid, uid=uid)
    video = Video.get_one(vid)
    if not video:
        return error.VideoNotExist

    return {'video': video.format()}


@app.route("/videos/categories", methods=("GET",))
@util.jsonapi()
def video_categories():
    """获取游戏下所有有视频的视频分类(GET)

    :uri: /videos/categories
    :param: game_id: 游戏ID
    :return: {'categories': <VideoCategory>list}
    """
    gid = request.values.get('game_id', None)
    if not gid:
        return error.InvalidArguments

    cate_ids = VideoCategory.all_category_ids()
    categories = []
    for cid in cate_ids:
        if CategoryVideo.category_game_video_count(cid, gid):
            category = VideoCategory.get_one(cid)
            categories.append(category.format())

    return {'categories': categories}


@app.route("/videos/category_videos", methods=("GET",))
@util.jsonapi()
def category_videos():
    """获取游戏下某个视频分类的所有视频(GET)

    :uri: /videos/category_videos
    :param: category_id: 分类ID
    :param: game_id: 游戏ID
    :param maxs: 最后时间, 0代表当前时间, 无此参数按page来分页
    :param page: 页码(数据可能有重复, 建议按照maxs分页)
    :param nbr: 每页数量
    :return: {'videos': <Video>list, 'end_page': bool, 'maxs': timestamp}
    """
    cid = request.values.get('category_id', None)
    gid = request.values.get('game_id', None)
    maxs = request.values.get('maxs', None)
    maxs = time.time() if maxs is not None and int(float(maxs)) == 0 else maxs and float(maxs)
    page = int(request.values.get('page', 1))
    pagesize = int(request.values.get('nbr', 10))

    if not cid or not gid:
        return error.InvalidArguments

    videos = list()
    vids = list()
    while len(videos) < pagesize:
        vids = CategoryVideo.category_game_video_ids(cid, gid, page, pagesize, maxs)
        ex_fields = ['is_favored', 'is_liked', 'author__is_followed', 'game__subscribed']
        videos.extend([v.format(exclude_fields=ex_fields) for v in Video.get_list(vids)])

        # 如果按照maxs分页, 不足pagesize个记录则继续查询
        if maxs is not None:
            obj = Video.get_one(vids[-1], check_online=False) if vids else None
            maxs = obj.create_at if obj else 1000
            if len(vids) < pagesize:
                break
        else:
            break

    return {'videos': videos, 'end_page': len(vids) != pagesize, 'maxs': maxs}


@app.route("/videos/topics", methods=("GET",))
@util.jsonapi()
def video_topics():
    """获取所有有视频的专题分类(GET)

    :uri: /videos/categories
    :return: {'topics': <VideoTopic>list}
    """
    topic_ids = VideoTopic.all_topic_ids()
    topics = []
    for tid in topic_ids:
        if TopicVideo.topic_video_count(tid):
            topic = VideoTopic.get_one(tid)
            topics.append(topic.format())

    return {'topics': topics}


@app.route("/videos/topic_videos", methods=("GET",))
@util.jsonapi()
def topic_videos():
    """获取专题所有视频(GET)

    :uri: /videos/topic_videos
    :param: topic_id: 专题ID
    :param maxs: 最后时间, 0代表当前时间, 无此参数按page来分页
    :param page: 页码(数据可能有重复, 建议按照maxs分页)
    :param nbr: 每页数量
    :return: {'videos': <Video>list, 'end_page': bool, 'maxs': timestamp}
    """
    tid = request.values.get('topic_id', None)
    maxs = request.values.get('maxs', None)
    maxs = time.time() if maxs is not None and int(float(maxs)) == 0 else maxs and float(maxs)
    page = int(request.values.get('page', 1))
    pagesize = int(request.values.get('nbr', 10))

    if not tid:
        return error.InvalidArguments

    topic = VideoTopic.get_one(tid)
    if not topic:
        return error.VideoTopicNotExist
    topic = topic.format()

    videos = list()
    vids = list()
    while len(videos) < pagesize:
        vids = TopicVideo.topic_video_ids(tid, page, pagesize, maxs)
        ex_fields = ['is_favored', 'is_liked', 'author__is_followed', 'game__subscribed']
        videos.extend([v.format(exclude_fields=ex_fields) for v in Video.get_list(vids)])

        # 如果按照maxs分页, 不足pagesize个记录则继续查询
        if maxs is not None:
            obj = Video.get_one(vids[-1], check_online=False) if vids else None
            maxs = obj.create_at if obj else 1000
            if len(vids) < pagesize:
                break
        else:
            break

    return {'videos': videos, 'topic': topic, 'end_page': len(vids) != pagesize, 'maxs': maxs}
