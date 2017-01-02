# -*- coding: utf8 -*-
from flask import Blueprint, request
from wanx.models.activity import ActivityConfig, VoteVideo, ActivityVideo, ShareActivityConfig, UserShareActivityLog
from wanx.models.game import GameActivity
from wanx.base import util, error
from wanx.base.xredis import Redis
from wanx.models.user import UserShare
from wanx.models.video import TopicVideo

activity = Blueprint("activity", __name__, url_prefix="/activity")


@activity.route('/<string:aid>/config', methods=['GET'])
@util.jsonapi()
def activity_config(aid):
    """获取活动配置接口(GET)

    :uri: /activity/<string:aid>/config
    :return: {"activity_games": list, "status": string, "buttons": list, "activity_config": Object}
    """

    activity_games = GameActivity.get_by_aid(aid)
    activity_games = [game.format() for game in activity_games]

    status = ActivityConfig.activity_status(aid)

    activity_config = ActivityConfig.get_one(aid)

    if activity_config:
        activity_config = activity_config.format()

    return {"activity_games": activity_games, "status": status, "buttons": [],
            'activity_config': activity_config}


@activity.route('/video/config/<string:vid>', methods=['GET'])
@util.jsonapi()
def activity_video_config(vid):
    """获取app内视频的活动相关配置

    :uri: activity/video/config/<string:vid>
    :return:{"activity": Object, "is_voted": bool, "is_join": bool, "activity_status": bool}
    """
    user = request.authed_user
    params = request.values
    device = params.get('device', None)
    uid = user and str(user._id)

    activity = dict()
    is_join = False
    activity_status = False

    activity_video = ActivityVideo.get_activity_video_by_vid(vid)
    if activity_video:
        is_join = True
        aid = activity_video["activity_id"]
        activity_config = ActivityConfig.get_one(aid, check_online=False)
        if not activity_config.online:
            activity_status = False
        else:
            activity_status = True
        activity = activity_config.format()

    is_voted = True if VoteVideo.get_vote(uid, device, vid) else False
    return {"activity": activity, "is_voted": is_voted, "is_join": is_join,
            "activity_status": activity_status}


@activity.route('/share/config', methods=['GET', 'POST'])
@util.jsonapi()
def share_activity_config():
    """
    分享活动
    :uri: /activity/share/config
    :param: aid 活动ID
    :param: device 设备ID
    :return:{'activity': ShareActivityConfig}
    """
    user = request.authed_user
    params = request.values
    aid = params.get('aid', None)
    device = params.get('device', None)
    uid = user and str(user._id)

    if not aid or not device:
        return error.InvalidArguments

    activity = ShareActivityConfig.get_one(aid, check_online=True)
    if not activity:
        return error.ActivityNotExist

    return {'activity': activity.format(uid, device)}


@activity.route('/share/rewards', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def share_activity_rewards():
    """
    请求分享活动奖励
    :uri: /activity/share/rewards
    :param: aid 活动ID
    :param: device 设备ID
    :return:
    """
    user = request.authed_user
    params = request.values
    aid = params.get('aid', None)
    device = params.get('device', None)
    uid = str(user._id)

    if not aid or not device:
        return error.InvalidArguments

    activity = ShareActivityConfig.get_one(aid, check_online=True)
    if not activity:
        return error.ActivityNotExist

    if not activity.get_left_today():
        return error.UserTrafficZero

    shared = UserShareActivityLog.check_user_activity(aid, user.phone, device)
    if shared:
        return error.UserTrafficExists

    # 获取分享活动的视频id
    vids = TopicVideo.topic_video_ids(activity.share_video_topic, 1, 99)

    # 查看用户活动期间内的分享数据
    user_shares = UserShare.get_user_shares_by_time(uid, activity.begin_at, activity.end_at)
    finished = False
    for us_id in user_shares:
        us = UserShare.get_one(us_id)
        if not us:
            continue
        if us.target_type not in ['video', 'url']:
            continue
        if us.target_type == 'url' and us.target_value != activity.share_url:
            continue
        if us.target_type == 'video' and us.target_value not in vids:
            continue
        finished = True
        break
    # 如果活动期间，用户没有分享过，则不可领取
    if not finished:
        return error.UserTrafficInvalid(u'您还没有分享活动规定的URL或视频')

    key = 'lock:share:activity:%s' % (uid)
    with util.Lockit(Redis, key) as locked:
        if locked:
            return error.UserTrafficInvalid(u'领取分享活动奖励失败')

        # 更新活动剩余奖励
        data = {'$set': {'left_num': activity.left_num - 1, 'use_num': activity.use_num + 1}}
        activity.update_model(data)

        # 创建用户参与分享活动记录
        usa_log = UserShareActivityLog.init()
        usa_log.activity = activity._id
        usa_log.owner = user._id
        usa_log.phone = user.phone
        usa_log.device = device
        usa_log.create_model()

        # 增加当日已领取次数
        ShareActivityConfig.incr_used_today(aid)

    return {'ret': True}

