# -*- coding: utf8 -*-
from flask import request
from wanx import app
from wanx.base import util, error, const
from wanx.base.xredis import Redis
from wanx.models.credit import UserCredit
from wanx.models.product import Product, UserProduct
from wanx.models.gift import Gift, UserGiftLog
from wanx.models.user import User
from wanx.models.msg import Message
from wanx.models.video import Video
from wanx.models.xconfig import Config
from wanx.platforms.xlive import Xlive

import datetime
import json


@app.route('/gifts/all_gifts', methods=['GET'])
@util.jsonapi()
def all_gifts():
    """获取所有可赠送礼物 (GET)

    :uri: /gifts/all_gifts
    :return: {'gifts': list, 'available_num': list}
    """
    user = request.authed_user
    if user:
        # 刷新每日免费礼物
        uc = UserCredit.get_or_create_user_credit(str(user._id))
        if uc.gift_at.date() < datetime.date.today():
            UserProduct.refresh_daily_free_gifts(str(user._id))

    gifts = []
    for gf in Gift.get_onsale_gifts():
        tmp = gf.format()
        # 每日免费礼物显示剩余数量
        if gf.credit_type == const.DAILY_FREE:
            if user:
                up = UserProduct.get_or_create_user_product(str(user._id), gf.product_id)
                tmp['free_num'] = up.gift_free
            else:
                tmp['free_num'] = 0
        gifts.append(tmp)

    available_num = Config.fetch('available_num', [1, 10, 30, 66, 188, 520], json.loads)
    available_num = sorted(available_num, reverse=True)
    return {'gifts': gifts, 'available_num': available_num}


@app.route('/gifts/user_gifts', methods=['GET'])
@util.jsonapi(login_required=True)
def user_gifts():
    """获取用户所有礼物 (GET&LOGIN)

    :uri: /gifts/user_gifts
    :return: {'gifts': list}
    """
    user = request.authed_user
    pdict = {}
    for p in Product.get_all_gifts():
        pdict[p.product_id] = p.format()

    uproducts = UserProduct.get_user_products(str(user._id))
    for up in uproducts:
        pdict[up.product_id].update(up.format())

    return {'gifts': pdict.values()}


@app.route('/gifts/send_gift', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def send_gift():
    """赠送礼物 (GET|POST&LOGIN)

    :uri: /gifts/send_gift
    :param user_id: 主播ID
    :param gift_id: 礼物ID
    :param num: 礼物数量
    :param gift_from: 礼物来源(1:直播, 2:录播)
    :param from_id:来源ID(直播ID或者录播视频ID)
    :return: {'ret: bool}
    """
    user = request.authed_user
    gift_id = int(request.values.get('gift_id'))
    to_user_id = request.values.get('user_id')
    num = int(request.values.get('num', 1))
    gift_from = int(request.values.get('gift_from'))
    from_id = request.values.get('from_id')
    user_ip = request.remote_addr
    device = request.values.get('device', None)

    if not gift_id or not to_user_id or num < 1 or not gift_from:
        return error.InvalidArguments

    if to_user_id == str(user._id):
        return error.GiftError('不能给自己赠送礼物哦')

    to_user = User.get_one(to_user_id, check_online=False)
    if not to_user:
        return error.UserNotExist('该视频没有主播')

    available_num = Config.fetch('available_num', [1, 10, 30, 66, 188, 520], json.loads)
    if num not in available_num:
        return error.GiftError('礼物数量不符合规则')

    gift = Gift.get_gift(gift_id)
    if not gift:
        return error.GiftError('该礼物不能赠送')

    ret = False
    key = 'lock:send_gift:%s' % (str(user._id))
    with util.Lockit(Redis, key) as locked:
        if locked:
            return error.GiftError('赠送礼物失败')

        ret = gift.send_to_user(str(user._id), to_user_id, num, gift_from, from_id)

    if isinstance(ret, error.ApiError):
        return ret

    # 录播发送消息到中心消息
    if ret and gift_from == const.FROM_RECORD:
        video = Video.get_one(from_id, check_online=False)
        if video:
            Message.send_gift_msg(str(user._id), from_id, 'gift')
            video.update_model({'$inc': {'gift_count': 1, 'gift_num': num}})

    # 直播发送广播信息
    if ret and gift_from == const.FROM_LIVE:
        data = dict(
            user_id=str(user._id),
            username=user.nickname or user.name,
            gift_name=gift.format()['product_name'],
            gift_image=gift.format()['product_image'],
            gift_num=num,
            event_id=from_id
        )
        Xlive.send_live_msg(data)

    # 营销数据入库经分  打赏活动
    from wanx.models.activity import ActivityConfig, ActivityVideo
    from wanx.platforms.migu import Marketing
    activity_config = None
    if gift_from == const.FROM_RECORD:
        activity_video = ActivityVideo.get_activity_video_by_vid(from_id)
        if activity_video:
            activity_config = ActivityConfig.get_one(activity_video['activity_id'])
    else:
        aids = ActivityConfig.get_by_type(const.FROM_LIVE)
        for a in ActivityConfig.get_list(aids):
            activity_config = a
            break
    if activity_config:
        data_dict = dict(
            cmd="deliver_gift",
            opt="{0}/{1}".format(gift.gold_price, to_user_id),
            deviceid=request.values.get('device', ''),
            mobile=user.phone,
            source=request.values.get('source', 'activity'),
            activityid=str(activity_config['_id']),
            activityname=activity_config['name']
        )
        Marketing.jf_report(data_dict)
    return {'ret': ret}


@app.route('/gifts/top_users', methods=['GET', 'POST'])
@util.jsonapi()
def gift_top_users():
    """获取赠送主播礼物用户排行 (GET|POST&LOGIN)

    :uri: /gifts/top_users
    :param user_id: 主播ID
    :param page: 页码
    :param nbr: 每页数量
    :return: {'users: list, 'end_page': bool}
    """
    user = request.authed_user
    page = int(request.values.get('page', 1))
    pagesize = int(request.values.get('nbr', 10))
    user_id = request.values.get('user_id')
    if not user_id:
        error.InvalidArguments

    uids = UserGiftLog.get_top_sender_ids(user_id, page, pagesize)
    users = []
    for uid, gold in uids:
        user = User.get_one(uid).format(exclude_fields=['is_followed'])
        user['total_gold'] = gold
        users.append(user)

    return {'users': users, 'end_page': len(uids) != pagesize}
