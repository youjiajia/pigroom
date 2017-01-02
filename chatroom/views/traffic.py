# -*- coding: utf8 -*-
from bson.objectid import ObjectId
from flask import request
from wanx.models.video import Video
from wanx.models.user import UserTrafficLog
from wanx.models.activity import ActivityConfig
from wanx import app
from wanx.base.xredis import Redis
from wanx.base import error, const, util
from wanx.platforms import Traffic
from wanx.base.log import print_log
import uuid
import re


# @app.route('/traffic', methods=['GET', 'POST'])
# @util.jsonapi(login_required=True)
# def traffic():
#     """流量赠送 (GET&POST&LOGIN)
#
#     :uri: /traffic
#     :param user_id: 分享目标所有者的id
#     :param target_id: 分享目标id
#     :param traffic_type: 流量类型, 首次登录:first_login ; 视频分享:video_share
#     :param platform: 分享平台
#     :returns: {"message": string}
#     """
#     user = request.authed_user
#     params = request.values
#     uid = params.get('user_id', None)
#     target_id = params.get('target_id', None)
#     platform = params.get('platform', None)
#     traffic_type = params.get('traffic_type', None)
#
#     if 'video_share' == traffic_type:
#         # if not uid or not timestamp or not sign or not vid:
#         #     return error.InvalidArguments
#
#         if uid != str(user._id):
#             return error.UserTrafficInvalid
#
#         video = Video.get_one(str(target_id))
#         if not video:
#             return error.VideoNotExist
#
#     elif 'first_login' == traffic_type:
#         pass
#     else:
#         return error.InvalidArguments
#
#     utl = UserTrafficLog.get_traffic_by_type(str(user._id), traffic_type)
#     if utl:
#         return error.UserTrafficExists
#
#     key = 'lock:traffic:%s:%s' % (user._id, traffic_type)
#     with util.Lockit(Redis, key) as locked:
#         if locked:
#             return error.UserTrafficInvalid
#         utl = UserTrafficLog.init()
#         utl.source = ObjectId(str(user._id))
#         utl.target = ObjectId(str(target_id)) if target_id else None
#         utl.traffic_type = traffic_type
#         utl.status = const.TRAFFIC_PROCESS
#         utl.platform = platform
#         utl.order_id = uuid.uuid1().get_hex()[:20]
#         utl.traffic_amount = const.TRAFFIC.get(traffic_type, 0)
#         utl.create_model()
#     return {"message": "你已经成功分享视频, 恭喜你获得免费流量150M, 礼物将以光速飞到你的碗里去哦, 请注意查收!"}


@app.route('/traffic/send', methods=['GET', 'POST'])
@util.jsonapi(login_required=True, verify=False)
def traffic_send():
    """发放流量 (GET|POST&LOGIN)

    :uri: /traffic/send
    :param traffic_type: (first_login, video_share)
    :returns: {'message': str}
    """
    user = request.authed_user
    traffic_type = request.values.get('traffic_type', None)
    device = request.values.get('device', None)

    status = ActivityConfig.activity_status()
    if const.ACTIVITY_PAUSE == status:
        print_log('app_traffic', '[%s][%s]: activity is pause' % (traffic_type, user.phone))
        return error.TrafficSendFail(u'小伙伴们太热情了，稍后再来吧！')
    elif const.ACTIVITY_END == status:
        print_log('app_traffic', '[%s][%s]: activity is end' % (traffic_type, user.phone))
        return error.UserTrafficZero(u'亲,我们的奖品已经送完啦,下次要早点来哦!')

    utl = UserTrafficLog.get_traffic_by_type(str(user._id), traffic_type)
    if not utl and traffic_type == 'video_share':
        print_log('app_traffic', '[video_share][%s]: UserTrafficExists' % user.phone)
        return error.UserTrafficExists(u'亲,你还没有分享自己的作品哦,赶快去分享你的游戏视频,再来领取吧!')
    elif utl and utl.status in [const.TRAFFIC_SUCCESS, const.TRAFFIC_RECEIVED_SUCCESS,
                                const.TRAFFIC_RECEIVED_PROCESS]:
        print_log('app_traffic', '[%s][%s]: TrafficExists' % (traffic_type, user.phone))
        return error.TrafficExists

    utl_device = UserTrafficLog.get_traffic_by_device(device, traffic_type)
    if utl_device:
        print_log('app_traffic', '[%s][%s][%s]: device repeat' % (traffic_type, user.phone, device))
        return error.UserTrafficInvalid(u'亲,同一部终端只能领取一次流量哦!')

    utl_count = UserTrafficLog.traffic_count_by_type(traffic_type)
    if utl_count and utl_count > const.TRAFFIC_CATEGORY_NUM.get(traffic_type, None):
        print_log('app_traffic', '[%s][%s]: UserTrafficZero' % (traffic_type, user.phone))
        return error.UserTrafficZero(u'亲,我们的奖品已经送完啦,下次要早点来哦!')

    key = 'lock:traffic:%s:%s' % (user.phone, utl.order_id)
    with util.Lockit(Redis, key) as locked:
        if locked:
            return error.TrafficSendFail
        # 移动接口返回
        if Traffic.send_traffic(utl.order_id, user.phone):
            utl.update_model({'$set': {'status': const.TRAFFIC_SUCCESS, 'device': device}})
        else:
            utl.update_model({'$set': {'status': const.TRAFFIC_FAIL}})
            return error.TrafficSendFail(u'小伙伴们太热情了，稍后再来吧！')
    return {"message": "你已经成功分享视频, 恭喜你获得免费流量150M, 礼物将以光速飞到你的碗里去哦, 请注意查收!"}


@app.route('/traffic/search', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def traffic_search():
    """流量查询接口(GET|POST&LOGIN)

    :uri: /traffic/search
    :param: traffic_type: (first_login, video_share)
    :returns: {taffict: taffic_status}  0:到账成功  -1:到账失败
    """
    user = request.authed_user
    traffic_type = request.values.get('traffic_type', None)

    utl = UserTrafficLog.get_traffic_by_type(str(user._id), traffic_type)
    _status = Traffic.query_traffic(utl.order_id)
    traffic_status = -1
    # 0＝成功，-1 = 失败, 1 = 正在处理中  该接口返回含义与充值接口不同，代表提交到上游接口的状态。
    # 该接口返回成功仅代表上游接口成功处理（多数情况为成功送出流量，个别省份只能代表已成功收到请求）
    if _status == '0':
        utl.update_model({'$set': {'status': const.TRAFFIC_RECEIVED_SUCCESS}})
        traffic_status = 0
    elif _status == '1':
        utl.update_model({'$set': {'status': const.TRAFFIC_RECEIVED_PROCESS}})
    else:
        utl.update_model({'$set': {'status': const.TRAFFIC_RECEIVED_FAIL}})
    return {'traffic_status': traffic_status}


@app.route('/traffic/message', methods=['GET', 'POST'])
def traffic_message():

    xml = request.data
    if not xml:
        return const.FAIL_XML
    action = re.compile(r'&lt;ACTION&gt;(\S+)&lt;/ACTION&gt;')
    _action = action.findall(xml)
    requestid = re.compile(r'&lt;RequestID&gt;(\S+)&lt;/RequestID&gt;')
    _requestid = requestid.findall(xml)
    resultcode = re.compile(r'&lt;ResultCode&gt;(\S+)&lt;/ResultCode&gt;')
    _resultcode = resultcode.findall(xml)

    if not _action:
        return const.FAIL_XML
    if not _requestid:
        return const.FAIL_XML
    else:
        utl = UserTrafficLog.get_traffic_by_orderid(_requestid[0])
    if not utl:
        return const.FAIL_XML
    if not _resultcode:
        # 判断是否符合活动状态
        return const.FAIL_XML
    if _resultcode[0] == '0':
        utl.update_model({'$set': {'status': const.TRAFFIC_RECEIVED_SUCCESS}})
    return const.SUCCESS_XML
