# -*- coding: utf8 -*-
from bson.objectid import ObjectId
from flask import request, Blueprint

from wanx.base.log import print_log
from wanx.models.task import UserTask, JOIN_COLLECT
from wanx.models.video import Video
from wanx.models.activity import ActivityConfig, ActivityVideo, VoteVideo, Mteam, VoteMteam
from wanx.models.game import GameActivity
from wanx.base import util, error
from wanx.base.guard import Guard
from wanx.base.xredis import Redis

import datetime
import time

video = Blueprint("video", __name__, url_prefix="/activity")


@video.route('/<string:aid>/compete_videos', methods=['GET'])
@util.jsonapi(login_required=True)
def compete_videos(aid):
    """获取可参赛视频(GET&LOGIN)

    :uri: /activity/<string:aid>/compete_videos
    :param page: 页数
    :param nbr: 每页数量
    :return: {'videos': list, 'max_video': int, 'end_page': bool}
    """
    params = request.values
    user = request.authed_user
    page = int(params.get('page', 1))
    pagesize = int(params.get('nbr', 10))

    activity_config = ActivityConfig.get_one(str(aid), check_online=False)
    if not activity_config:
        return error.ActivityNotExist

    activity_videos = ActivityVideo.user_compete_video_ids(aid, str(user._id))
    avids = [a['video_id'] for a in activity_videos]

    videos = list()
    gids = GameActivity.game_activity_ids(aid)
    gids = [ObjectId(_gid) for _gid in gids]

    vids = Video.activity_video_ids(str(user._id), pagesize, page, gids, activity_config)
    vids = [vid for vid in vids]
    videos.extend([v.format() for v in Video.get_list(vids)])
    # 允许参赛最大视频数
    max_video = activity_config.max_video - len(avids)

    return {'videos': videos, 'end_page': len(vids) != pagesize, 'max_video': max_video}


@video.route('/<string:aid>/new-video', methods=['POST'])
@util.jsonapi(login_required=True)
def activity_create_video(aid):
    """创建活动视频 (POST&LOGIN)

    :uri: activity/<string:aid>/new-video
    :param video_id: 原始视频id
    :returns: object
    """
    user = request.authed_user
    vid = request.values['video_id']
    video = Video.get_one(str(vid))
    if not video:
        return error.VideoNotExist

    if str(user._id) != str(video.author):
        return error.AuthFailed

    activity_video = ActivityVideo.get_activity_video_by_vid(vid)
    if activity_video:
        return error.ActivityVideoExist

    activity_video = ActivityVideo.init()
    activity_video.title = video.title
    activity_video.video_id = ObjectId(vid)
    activity_video.like_count = video.like
    activity_video.comment_count = video.comment_count
    activity_video.vv = video.vv
    activity_video.author = ObjectId(str(user._id))
    activity_video.activity_id = ObjectId(str(aid))
    activity_video.cover = video.cover
    activity_video.duration = video.duration
    activity_video.game = video.game

    avid = activity_video.create_model()
    video.update_model({'$set': {'activity_ids': [avid]}})

    # 任务检查
    if user:
        UserTask.check_user_tasks(str(user._id), JOIN_COLLECT, 1, str(video.game), str(aid))

    return ActivityVideo.get_one(avid, check_online=False).format()


@video.route('/<string:aid>/popular/videos', methods=['GET'])
@util.jsonapi()
def activity_popular_videos(aid):
    """获取人气视频

    :uri: activity/<string:aid>/popular/videos
    :param page: 页码
    :param nbr: 每页数量
    :param device: 终端ID
    :returns: {'activity_videos': list, 'end_page': bool, 'activity_config': Object }
    """

    params = request.values
    page = int(params.get('page', 1))
    pagesize = int(params.get('nbr', 10))

    activity_videos = list()
    activity_config = ActivityConfig.get_one(str(aid), check_online=False)
    if not activity_config:
        return error.ActivityNotExist
    sort = activity_config.sort

    avids = ActivityVideo.popular_video_ids(aid, sort, page, pagesize)
    activity_videos.extend([v.format() for v in ActivityVideo.get_list(avids)])
    return {'activity_videos': activity_videos, 'end_page': len(avids) != pagesize,
            'activity_config': activity_config.format()}


@video.route('/<string:aid>/video/current', methods=['GET'])
@util.jsonapi()
def latest_video(aid):
    """获取最新参赛视频

    :uri: activity/<string:aid>/video/current
    :param maxs: 最后时间, 0代表当前时间
    :param nbr: 每页数量
    :param device: 终端ID
    :returns: {'activity_videos': list, 'end_page': bool, 'activity_config': Object,
               'maxs': timestamp}
    """

    params = request.values
    maxs = params.get('maxs', None)
    maxs = time.time() if maxs is not None and int(float(maxs)) == 0 else maxs and float(maxs)
    pagesize = int(params.get('nbr', 10))

    activity_config = ActivityConfig.get_one(aid, check_online=False)
    if not activity_config:
        return error.ActivityNotExist

    avideos = list()
    avids = list()
    while len(avideos) < pagesize:
        avids = ActivityVideo.latest_video_ids(aid, pagesize, maxs)
        avideos.extend([v.format() for v in ActivityVideo.get_list(avids)])
        # 如果按照maxs分页, 不足pagesize个记录则继续查询
        if maxs is not None:
            obj = ActivityVideo.get_one(avids[-1]) if avids else None
            maxs = obj.create_at if obj else 1000
            if len(avids) < pagesize:
                break
        else:
            break
    return {'activity_videos': avideos, 'end_page': len(avids) != pagesize,
            'activity_config': activity_config.format(), 'maxs': maxs}


@video.route('/<string:aid>/videos', methods=['GET'])
@util.jsonapi(login_required=True)
def user_videos(aid):
    """获取我的参赛视频(GET&LOGIN)

    :uri: activity/<string:aid>/videos
    :param type: 活动结束时参数(type=end)
    :param device: 终端ID
    :return: {'activity_videos': list, 'activity_config': Object}
    """
    user = request.authed_user
    type = request.values.get('type', None)

    activity_config = ActivityConfig.get_one(str(aid), check_online=False)
    if not activity_config:
        return error.ActivityNotExist
    sort = activity_config.sort

    activity_videos = ActivityVideo.user_compete_video_ids(aid, user._id)
    if not type:
        top_compete_videos = ActivityVideo.top_video_ids(aid, sort)
    videos = list()

    for activity_video in activity_videos:
        avid = str(activity_video['_id'])
        activity_video = ActivityVideo.get_one(avid)
        activity_video = activity_video.format()
        if type:
            videos.append(activity_video)
            continue

        if avid in top_compete_videos:
            top = top_compete_videos.index(avid)
            activity_video['top'] = top + 1
            videos.append(activity_video)
        else:
            continue
    return {'activity_videos': videos, 'activity_config': activity_config.format()}


@video.route('/<string:aid>/delete/videos', methods=['POST'])
@util.jsonapi(login_required=True)
def delete_videos(aid):
    """删除我的参赛视频(POST&LOGIN)

    :uri: activity/<string:aid>/delete/videos
    :param activity_video: 活动参赛视频id
    :return: {}
    """
    user = request.authed_user

    avid = request.values.get('activity_video', None)
    activity_video = ActivityVideo.get_one(avid)
    if not activity_video:
        return error.ActivityVideoNotExist
    if str(activity_video.author) != str(user._id):
        return error.AuthFailed

    activity_video.delete_model()
    return {}


@video.route('/<string:aid>/top/videos', methods=['GET'])
@util.jsonapi()
def activity_top_videos(aid):
    """获取结束时获奖视频

    :uri: activity/<string:aid>/top/videos
    :param page: 页码
    :param nbr: 每页数量
    :returns: {'activity_videos': list, 'end_page': bool, 'activity_config': Object }
    """

    params = request.values
    page = int(params.get('page', 1))
    pagesize = int(params.get('nbr', 10))

    activity_videos = list()
    activity_config = ActivityConfig.get_one(str(aid), check_online=False)
    if not activity_config:
        return error.ActivityNotExist

    avids = ActivityVideo.top_video_end(aid, page, pagesize, activity_config)
    activity_videos.extend([a.format() for a in ActivityVideo.get_list(avids)])
    return {'activity_videos': activity_videos, 'end_page': len(avids) != pagesize,
            'activity_config': activity_config.format()}


@video.route('/<string:aid>/manual/top', methods=['GET'])
@util.jsonapi()
def activity_top(aid):
    """获取结束时获奖视频(手动)

    :uri: activity/<string:aid>/manual/top
    :param page:
    :param nbr:
    :return: {'activity_videos': list, 'end_page': bool}
    """

    params = request.values
    page = int(params.get('page', 1))
    pagesize = int(params.get('nbr', 10))

    activity_videos = list()
    activity_config = ActivityConfig.get_one(str(aid), check_online=False)
    if not activity_config:
        return error.ActivityNotExist

    avids = ActivityVideo.get_manual_top(aid, page, pagesize)
    activity_videos.extend([a.format() for a in ActivityVideo.get_list(avids, check_online=False)])
    return {'activity_videos': activity_videos, 'end_page': len(avids) != pagesize}


@video.route('/video/<string:vid>', methods=['GET'])
@util.jsonapi()
def get_activity_video(vid):
    """获取参赛视频信息(GET&LOGIN)

    :uri: activity/video/<string:vid>
    :param device: 终端ID
    :return: {'activity_video': Object, 'activity_config': Object}
    """

    activity_video = ActivityVideo.get_activity_video_by_vid(vid)
    if not activity_video:
        return error.ActivityVideoNotExist
    activity_config = ActivityConfig.get_one(activity_video['activity_id'])
    top_compete_videos = ActivityVideo.top_video_ids(activity_video['activity_id'],
                                                     activity_config.sort)

    top = top_compete_videos.index(str(activity_video['_id']))
    activity_video = activity_video.format()
    activity_video['top'] = top + 1

    return {'activity_video': activity_video, 'activity_config': activity_config.format()}


@video.route('/vote', methods=['POST'])
@util.jsonapi(login_required=True, verify=False)
def activity_vote():
    """活动投票

    :uri: activity/vote
    :param source: 投票来源(app_play, activity, activity_share, video_share)
    :param device: 设备唯一ID
    :param video_id: 视频ID
    :param ut: 用户ut
    :return: {'vote_count': int}
    """
    user = request.authed_user
    params = request.values.to_dict()

    if not Guard.verify_sig(params):
        return error.InvalidRequest

    vid = params.get('video_id', None)
    source = params.get('source', None)
    device = params.get('device', None)
    uid = user and str(user._id)

    if not vid or not source or not device:
        return error.InvalidArguments

    # 增加ip限制，每个ip每天限制20次
    user_ip = request.remote_addr
    ip_key = 'ip_limit:%s:%s:%s' % (user_ip, vid, str(datetime.date.today()))
    ip_limit = Redis.incr(ip_key)
    if ip_limit == 1:  # 第一次设置key过期时间
        Redis.expire(ip_key, 86400)

    if ip_limit > 20:
        return error.ActivityVideoNotExist("超出IP限制")

    video = Video.get_one(vid)
    if not video:
        return error.VideoNotExist

    activity_video = ActivityVideo.get_activity_video_by_vid(vid)
    if not activity_video:
        return error.ActivityVideoNotExist("该视频未参赛")

    vote_count = activity_video['vote']
    activity_id = activity_video['activity_id']

    activity_config = ActivityConfig.get_one(activity_id)
    if not activity_config or not activity_config.online:
        return error.ActivityEnd

    is_voted = True if VoteVideo.get_vote(uid, device, vid) else False
    if is_voted:
        return error.VoteVideoLimited

    vote = VoteVideo.get_vote(uid=uid, device=device, vid=vid)
    if not vote:
        key = 'lock:vote_video:%s:%s' % (device, vid)
        with util.Lockit(Redis, key) as locked:
            if locked:
                return error.VoteVideoFailed
            vote = VoteVideo.init()
            vote.device = device
            vote.source = source
            vote.author = ObjectId(uid)
            vote.target = ObjectId(vid)
            vote.activity = ObjectId(activity_id)
            vote.create_model()
            # 票数加1
            vote_count = vote_count + 1

    # 营销数据入库经分  投票活动
    from wanx.platforms.migu import Marketing
    data_dict = dict(
            cmd="vote",
            opt=vid,
            deviceid=params.get('device', ''),
            mobile=user.phone,
            source=params.get('source', 'activity'),
            activityid=str(activity_video['activity_id']),
            activityname=activity_config['name']
    )
    Marketing.jf_report(data_dict)

    return {'vote_count': vote_count}


@video.route('/team_vote', methods=['POST'])
@util.jsonapi(login_required=True, verify=False)
def activity_team_vote():
    """战队投票

    :uri: activity/team_vote
    :param source: 投票来源(app_play, activity, activity_share, video_share)
    :param device: 设备唯一ID
    :param team_id: 战队ID
    :param ut: 用户ut
    :return: {'team_vote_count': int}
    """
    user = request.authed_user
    print_log('activity/team_vote', '[user]: {0}'.format(user))
    
    params = request.values.to_dict()

    tid = params.get('team_id', None)
    source = params.get('source', None)
    device = params.get('device', None)
    uid = user and str(user._id)

    if not tid or not source or not device:
        return error.InvalidArguments

    # 增加ip限制，每个ip每天限制20次
    user_ip = request.remote_addr
    ip_key = 'ip_limit:%s:%s:%s' % (user_ip, tid, str(datetime.date.today()))
    ip_limit = Redis.incr(ip_key)
    if ip_limit == 1:  # 第一次设置key过期时间
        Redis.expire(ip_key, 86400)

    if ip_limit > 20:
        return error.ActivityVideoNotExist("超出IP限制")

    mteam = Mteam.get_one(tid)
    if not mteam:
        return error.MteamNotExist

    vote_count = int(mteam['ticket'])
    mname = str(mteam['mname'])

    vote = VoteMteam.get_vote(uid=uid, device=device, tid=tid)
    if not vote:
        key = 'lock:vote_mteam:%s:%s' % (device, tid)
        with util.Lockit(Redis, key) as locked:
            if locked:
                return error.VoteVideoFailed
            vote = VoteMteam.init()
            vote.device = device
            vote.source = source
            vote.author = ObjectId(uid)
            vote.target = ObjectId(tid)
            vote.mname = ObjectId(mname)
            vote.create_model()
            # 票数加1
            vote_count = vote_count + 1
    return {'vote_count': vote_count}
