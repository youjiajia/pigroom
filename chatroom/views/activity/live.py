# -*- coding: utf8 -*-
from flask import Blueprint, request
from wanx.models.user import User
from wanx.models.live import Live_Activity
from wanx.models.activity import ActivityConfig, ActivityLiveMaster
from wanx.models.gift import UserGiftLog
from wanx.base import util, error

import time

live = Blueprint("live", __name__, url_prefix="/activity")


@live.route('/live/hot_user/<string:aid>', methods=['GET'])
@util.jsonapi()
def live_hot_user(aid):
    """获取热门主播

    :uri: activity/live/hot_user/<string:aid>
    :param maxs: 分页标示, 0最新
    :param nbr: 每页数量
    :returns: {'hot_users': list, 'end_page': bool,  'maxs': long}
    """

    params = request.values
    maxs = params.get('maxs', 0)
    maxs = time.time() * 10000000000 if maxs is not None and int(float(maxs)) == 0 else maxs and float(maxs)
    pagesize = int(params.get('nbr', 10))

    activity_config = ActivityConfig.get_one(aid, check_online=True)
    if not activity_config:
        return error.ActivityNotExist

    hot_users = list()
    while len(hot_users) < pagesize:
        user_scores = Live_Activity.get_live_hot_user(aid, pagesize, activity_config.begin_at, activity_config.end_at, maxs)
        for us in user_scores:
            user = User.get_one(str(us[0]), check_online=True)
            if user:
                total_gold = UserGiftLog.get_user_total_gold(str(us[0]), activity_config.begin_at, activity_config.end_at)
                hot_users.append({'user': user.format(), 'gold': total_gold, 'top': us[2]})
        # 如果按照maxs分页, 不足pagesize个记录则继续查询
        obj = user_scores[-1] if user_scores else None
        maxs = obj[1] if obj else time.time() * 10000000000
        if len(user_scores) < pagesize:
            break

    return {'hot_users': hot_users, 'end_page': len(hot_users) != pagesize, 'maxs': maxs}


@live.route('/live/new_user/<string:aid>', methods=['GET'])
@util.jsonapi()
def live_new_user(aid):
    """获取新秀主播

    :uri: activity/live/new_user/<string:aid>
    :param maxs: 分页标示, 0最新
    :param nbr: 每页数量
    :returns: {'new_users': list, 'end_page': bool,  'maxs': long}
    """
    params = request.values
    maxs = params.get('maxs', 0)
    maxs = time.time() if maxs is not None and int(float(maxs)) == 0 else maxs and float(maxs)
    pagesize = int(params.get('nbr', 10))

    activity_config = ActivityConfig.get_one(aid, check_online=True)
    if not activity_config:
        return error.ActivityNotExist

    users = list()
    uids = list()
    while len(users) < pagesize:
        uids = Live_Activity.get_live_new_user(aid, pagesize, maxs)
        for u in User.get_list(uids):
            top = Live_Activity.get_live_user_top(aid, str(u._id), activity_config.begin_at, activity_config.end_at)
            total_gold = UserGiftLog.get_user_total_gold(u._id, activity_config.begin_at, activity_config.end_at)
            users.append({'user': u.format(), 'gold': total_gold, 'top': top})
        # 如果按照maxs分页, 不足pagesize个记录则继续查询
        if maxs is not None:
            obj = User.get_one(uids[-1]) if uids else None
            maxs = obj.create_at if obj else 1000
            if len(uids) < pagesize:
                break
        else:
            break
    return {'new_users': users, 'end_page': len(uids) != pagesize, 'maxs': maxs}


@live.route('/live/<string:aid>/user/info', methods=['GET'])
@util.jsonapi(login_required=True)
def live_user_info(aid):
    """获取主播信息

    :uri: activity/live/<string:aid>/user/info
    :returns: {'user': Object, 'top': int, 'gold': int}
    """

    user = request.authed_user
    activity_config = ActivityConfig.get_one(aid, check_online=True)
    if not activity_config:
        return error.ActivityNotExist
    top = Live_Activity.get_live_user_top(aid, str(user._id), activity_config.begin_at, activity_config.end_at)
    total_gold = UserGiftLog.get_user_total_gold(str(user._id), activity_config.begin_at, activity_config.end_at)
    return {'user': user.format(), 'top': top, 'gold': total_gold}


@live.route('/live/search/<string:aid>', methods=['GET', 'POST'])
@util.jsonapi()
def search(aid):
    """搜索 (GET|POST)

    :uri: /activity/live/search/<string:aid>
    :param type: 搜索类型{'user':用户}
    :param keyword: 关键字
    :returns: {'user':list}
    """
    params = request.values
    stype = params.get('type', 'user')
    keyword = params.get('keyword', '')
    keyword = keyword.strip()

    if not stype or not keyword:
        return error.InvalidArguments

    users = list()

    activity_config = ActivityConfig.get_one(aid, check_online=True)
    if not activity_config:
        return error.ActivityNotExist

    if stype in ['user']:
        uids = User.search(keyword)
        _uids = Live_Activity.get_activity_live_by_authors(aid, uids)
        for _uid in _uids:
            user = User.get_one(_uid).format()
            top = Live_Activity.get_live_user_top(aid, _uid, activity_config.begin_at, activity_config.end_at)
            gold= UserGiftLog.get_user_total_gold(_uid, activity_config.begin_at, activity_config.end_at)
            users.append({'user': user, 'top': top, 'gold': gold})

    return {'users': users}


@live.route('/live/recruit/check_user', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def check_user():
    """
    主播招募活动用户报名信息检查
    :uri: /activity/live/recruit/check_user
    :param: activity_id 活动ID
    :return: {'ret' : bool, 'user': ActivityLiveMaster}
    """
    user = request.authed_user
    params = request.values
    aid = params.get('activity_id', None)

    if aid is None:
        return error.InvalidArguments

    activity_config = ActivityConfig.get_one(aid, check_online=True)
    if not activity_config:
        return error.ActivityNotExist

    uid = str(user._id)
    alm_id = ActivityLiveMaster.check_activity_user(aid, uid)
    if not alm_id:
        return {'ret': False, 'user': None}
    author = ActivityLiveMaster.get_one(alm_id)
    return {'ret': True, 'user': author.format()}


@live.route('/live/recruit/join', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def join_in():
    """
    主播招募活动报名
    :uri: /activity/live/recruit/join
    :param: activity_id 活动ID
    :param: name 姓名
    :param: gender 性别
    :param: phone 联系电话
    :param: identity 身份证号码
    :param: content 个人宣言
    :return: {'ret' : bool, 'user': ActivityLiveMaster}
    """
    user = request.authed_user
    params = request.values
    aid = params.get('activity_id', None)
    name = params.get('name', None)
    gender = params.get('gender', None)
    phone = params.get('phone', None)
    identity = params.get('identity', None)
    content = params.get('content', None)

    if any(map(lambda x: x is None, [aid, name, gender, phone, identity, content])):
        return error.InvalidArguments

    activity_config = ActivityConfig.get_one(aid, check_online=True)
    if not activity_config:
        return error.ActivityNotExist

    uid = str(user._id)
    if ActivityLiveMaster.check_activity_user(aid, uid):
        return error.UserExists

    alm = ActivityLiveMaster.init()
    alm.activity_id = aid
    alm.user_id = uid
    alm.name = name
    alm.gender = gender
    alm.phone = phone
    alm.identity = identity
    alm.content = content
    alm.duration = 0
    alm.create_model()

    return {'ret': True, 'user': alm.format()}


@live.route('/live/recruit/latest', methods=['GET'])
@util.jsonapi()
def live_latest_user():
    """
    主播招募活动按最新报名时间排序的用户
    :uri: /activity/live/recruit/latest
    :param: activity_id 活动ID
    :param: maxs
    :return: {'duration_users': <ActivityLiveMaster> list}
    """
    params = request.values
    aid = params.get('activity_id', None)
    maxs = params.get('maxs', None)
    page = params.get('page', 1)
    pagesize = params.get('nbr', 10)

    if aid is None:
        return error.InvalidArguments

    activity_config = ActivityConfig.get_one(aid, check_online=True)
    if not activity_config:
        return error.ActivityNotExist

    uids = ActivityLiveMaster.latest_uids(aid, activity_config.end_at, page, pagesize, maxs)
    users = [u.format() for u in ActivityLiveMaster.get_list(uids)]

    return {'latest_users': users}

@live.route('/live/recruit/duration', methods=['GET'])
@util.jsonapi()
def live_duration_user():
    """
    主播招募活动按最高直播时长排序的用户
    :uri: /activity/live/recruit/duration
    :param: activity_id 活动ID
    :param: maxs
    :return: {'latest_users': <ActivityLiveMaster> list}
    """
    params = request.values
    aid = params.get('activity_id', None)
    maxs = params.get('maxs', None)
    page = params.get('page', 1)
    pagesize = params.get('nbr', 10)

    if aid is None:
        return error.InvalidArguments

    activity_config = ActivityConfig.get_one(aid, check_online=True)
    if not activity_config:
        return error.ActivityNotExist

    uids = ActivityLiveMaster.duration_uids(aid, activity_config.end_at, page, pagesize, maxs)
    users = [u.format() for u in ActivityLiveMaster.get_list(uids)]

    return {'duration_users': users}


