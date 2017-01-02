# -*- coding: utf8 -*-
import json
import time
from flask import request
from wanx import app
from wanx.base import util, error, const
from wanx.base.xredis import Redis
from wanx.base.log import print_log
from wanx.base.spam import Spam
from wanx.models.live import WatchLiveTask, WatchLiveTaskItem, LiveRedPacket, UserRedPacket, LiveRedPacketItem
from wanx.models.product import Product
from wanx.models.store import UserLiveOrder
from wanx.platforms import Migu
from wanx.platforms.migu import Marketing
from wanx.platforms.xlive import Xlive
from wanx.models.user import FriendShip
from wanx.models.game import LiveHotGame, UserSubGame, Game, UserPopularGame
from wanx.models.task import UserTask, PLAY_LIVE, SHARE_LIVE


@app.route('/lives/cate-games', methods=['GET'])
@util.jsonapi()
def get_category_games():
    """获取直播分类列表(游戏) (GET)

    :uri: /lives/cate-games
    :returns: {'games': list}
    """
    user = request.authed_user
    gids = LiveHotGame.hot_game_ids()
    if user:
        for sgid in UserSubGame.sub_game_ids(str(user._id)):
            if sgid not in gids:
                gids.append(sgid)

    games = [g.format() for g in Game.get_list(gids)]
    return {'games': games}


@app.route('/lives/hot_games', methods=['GET'])
@util.jsonapi()
def get_hot_games():
    """获取常用游戏列表(游戏) (GET)

        :uri: /lives/hot_games
        :returns: {'games': list}
        """
    user = request.authed_user
    if user:
        uid = UserPopularGame.get_user_id(user._id)
        gids = UserPopularGame.get_game_ids(user._id)
        if not gids:
            if uid:
                gids = None
            else:
                gids = LiveHotGame.hot_game_ids()
    else:
        gids = LiveHotGame.hot_game_ids()

    games = [g.format() for g in Game.get_list(gids)]
    return {'games': games}


@app.route('/lives/recommend', methods=['GET'])
@util.jsonapi()
def get_recommend_lives():
    """获取推荐的直播列表 (GET)

    :uri: /lives/recommend
    :returns: {'lives': list}
    """
    user = request.authed_user
    lives = list()
    ex_lids = list()
    if user:
        uids = FriendShip.following_ids(str(user._id))
        users_lives = Xlive.get_users_lives(uids)
        for ul in users_lives:
            ul['from_following'] = True
            ex_lids.append(ul['event_id'])

        lives.extend(users_lives)

    games_lives = Xlive.get_all_lives()
    games_lives = filter(lambda x: x['event_id'] not in ex_lids, games_lives)
    lives.extend(games_lives)
    ex_fields = ['user__is_followed', 'game__subscribed']
    lives = [Xlive.format(l, exclude_fields=ex_fields) for l in lives]
    return {'lives': lives}


@app.route('/lives/game', methods=['GET'])
@util.jsonapi()
def get_game_lives():
    """获取游戏的直播列表 (GET)

    :uri: /lives/game
    :param gid: 游戏ID
    :returns: {'lives': list}
    """
    gid = request.values.get('gid')
    lives = Xlive.get_game_lives(gid)
    ex_fields = ['user__is_followed', 'game__subscribed']
    lives = [Xlive.format(l, exclude_fields=ex_fields) for l in lives]
    return {'lives': lives}


@app.route('/lives/info', methods=['GET'])
@util.jsonapi()
def get_live_info():
    """获取直播信息 (GET)

    :uri: /lives/info
    :param live_id: 直播ID
    :return: {'live': object}
    """
    params = request.values
    live_id = params.get('live_id')
    os = params.get('os', None)
    channels = params.get('channels', None)
    version_code = int(params.get('version_code', 0))

    if not os or not version_code or live_id is None:
        return error.InvalidArguments

    live = Xlive.get_live(live_id)
    if not live:
        return error.LiveError('直播不存在')

    uid = None
    province = None
    user = request.authed_user
    if user:
        uid = str(user._id)
        UserTask.check_user_tasks(uid, PLAY_LIVE, 1)
        task_ids = WatchLiveTask.get_user_tids(uid)

        phone = str(user.phone)

        if user.province:
            province = user.provice

        if not user.province and util.is_mobile_phone(phone):
            province = Migu.get_user_info_by_account_name(phone)
            if not isinstance(province, error.ApiError):
                user.update_model({'$set': {'province': province}})
            else:
                province = None

    else:
        task_ids = WatchLiveTask.get_live_tids()

    task = None
    for b in WatchLiveTask.get_list(task_ids):
        if b.os and b.os not in ['all', os]:
            continue

        if (b.version_code_mix and b.version_code_mix > version_code) or \
                (b.version_code_max and b.version_code_max < version_code):
            continue

        if channels and b.channels and channels not in b.channels:
            continue

        if b.login == 'login' and (not uid or not b.user_in_group(str(b.group), uid)):
            continue

        if b.province and not province:
            continue

        if province and province not in b.province:
            continue

        task = b.format(uid)
        break

    red_packet, red_packet_count = None, 0
    _ids = UserRedPacket.user_red_packets(uid)
    for urp in UserRedPacket.get_list(_ids):
        if not LiveRedPacket.get_one(urp.active_id):
            continue
        if urp.source == 0:
            # 过滤掉所有直播间抽奖机会
            continue
        if urp.chance <= 0:
            continue
        if red_packet is None or red_packet.expire_at > urp.expire_at:
            red_packet = urp
        red_packet_count += 1
    red_packet = red_packet.format(red_packet_count) if red_packet else red_packet

    return {'live': Xlive.format(live, exclude_fields=['game__subscribed']),
            'task': task, 'red_packet': red_packet}


@app.route('/lives/share', methods=['GET'])
@util.jsonapi()
def share_live():
    """分享直播接口 (GET)

    :uri: /lives/share
    :param live_id: 直播ID
    :return: {'ret': bool}
    """
    user = request.authed_user
    live_id = request.values.get('live_id')
    live = Xlive.get_live(live_id)
    if not live:
        return error.LiveError('直播不存在')

    if user:
        UserTask.check_user_tasks(str(user._id), SHARE_LIVE, 1)

    return {'ret': True}


@app.route('/lives/play', methods=['GET'])
@util.jsonapi()
def play_live():
    """观看直播接口 (GET)

    :uri: /lives/play
    :param live_id: 直播ID
    :param os: 平台
    :param channels: 渠道（可选）
    :param version_code: 版本
    :return: {'ret': bool}
    """
    user = request.authed_user
    params = request.values
    live_id = params.get('live_id', None)
    os = params.get('os', None)
    channels = params.get('channels', None)
    version_code = int(params.get('version_code', 0))

    if not os or not version_code or live_id is None:
        return error.InvalidArguments

    live = Xlive.get_live(live_id)
    if not live:
        return error.LiveError('直播不存在')

    uid = None
    province = None
    if user:
        uid = str(user._id)
        UserTask.check_user_tasks(uid, PLAY_LIVE, 1)
        task_ids = WatchLiveTask.get_user_tids(uid)

        phone = str(user.phone)

        if user.province:
            province = user.provice

        if not user.province and util.is_mobile_phone(phone):
            province = Migu.get_user_info_by_account_name(phone)
            if not isinstance(province, error.ApiError):
                user.update_model({'$set': {'province': province}})
            else:
                province = None

    else:
        task_ids = WatchLiveTask.get_live_tids()

    task = None
    for b in WatchLiveTask.get_list(task_ids):
        if b.os and b.os not in ['all', os]:
            continue

        if (b.version_code_mix and b.version_code_mix > version_code) or \
                (b.version_code_max and b.version_code_max < version_code):
            continue

        if channels and b.channels and channels not in b.channels:
            continue

        if b.login == 'login' and (not uid or not b.user_in_group(str(b.group), uid)):
            continue

        if b.province and not province:
            continue

        if province and province not in b.province:
            continue

        task = b.format(uid)
        break

    red_packet, red_packet_count = None, 0
    _ids = UserRedPacket.user_red_packets(uid)
    for urp in UserRedPacket.get_list(_ids):
        if not LiveRedPacket.get_one(urp.active_id):
            continue
        if urp.source == 0:
            # 过滤掉所有直播间抽奖机会
            continue
        if urp.chance <= 0:
            continue
        if red_packet is None or red_packet.expire_at > urp.expire_at:
            red_packet = urp
        red_packet_count += 1
    red_packet = red_packet.format(red_packet_count) if red_packet else red_packet

    return {'ret': True, 'task': task, 'red_packet': red_packet}


@app.route('/lives/match', methods=['GET'])
@util.jsonapi()
def get_match_lives():
    """获取推荐的赛事直播列表 (GET)

    :uri: /lives/match
    :param live_user_id: 主播ID
    :param live_name: 主播间名称
    :returns: {'lives': list}
    """
    user_id = request.values.get('live_user_id')
    name = request.values.get('live_name')

    lives = Xlive.get_match_live(str(user_id), name)
    print_log('xlive', '[get_match_lives - lives]: {0}'.format(lives))

    if not lives:
        return error.LiveError('直播不存在')

    lives = [Xlive.format(l) for l in lives]

    return {'lives': lives}


@app.route('/lives/task', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def live_task():
    """观看直播时长任务 (GET)

    :uri: /lives/task
    :param task_id: 直播任务ID
    :param os: 平台
    :param channels: 渠道（可选）
    :param version_code: 版本号
    :param live_id: 直播间ID
    :return: {'ret': bool}
    """
    user = request.authed_user
    params = request.values
    task_id = params.get('task_id', None)
    os = params.get('os', None)
    channels = params.get('channels', None)
    version_code = int(params.get('version_code', 0))
    live_id = request.values.get('live_id')

    if not os or not version_code or not task_id or not live_id:
        return error.InvalidArguments

    uid = str(user._id)
    phone = str(user.phone)
    province = None
    if user.province:
        province = user.provice

    if not user.province and util.is_mobile_phone(phone):
        province = Migu.get_user_info_by_account_name(phone)
        if not isinstance(province, error.ApiError):
            user.update_model({'$set': {'province': province}})
        else:
            province = None
    # 避免出现跨天时出现没有任务的情况
    tids = WatchLiveTask.get_user_tids(uid)
    task = WatchLiveTask.get_one(task_id)
    if not task:
        return error.TaskError(u'观看直播时长任务不存在！')

    if task.os not in ['all', os]:
        return error.TaskError(u'不符合任务条件！')

    if (task.version_code_mix and task.version_code_mix > version_code) or \
            (task.version_code_max and task.version_code_max < version_code):
        return error.TaskError(u'不符合任务条件！')

    if channels and task.channels and channels not in task.channels:
        return error.TaskError(u'不符合任务条件！')

    if task.login == 'login' and (not uid or not task.user_in_group(str(task.group), uid)):
        return error.TaskError(u'不符合任务条件！')

    if task.province and not province:
        return error.TaskError(u'不符合任务条件！')

    if province and province not in task.province:
        return error.TaskError(u'不符合任务条件！')

    extra = dict(
        migu_id=user.partner_migu['id'],
        phone=user.phone,
        campaign_id=task.campaign_id
    )
    msg = u"恭喜%(name)s获得%(gift)s"

    def send_default_gift(uid, task_id, user, extra, msg):
        item = WatchLiveTaskItem.get_item_by_identity(task_id, 'default')
        if not item:
            return {'ret': False, 'task': task.format(uid), 'item': None}
        # 更新库存
        item.update_left()

        # 进行物品的发放
        product = Product.get_product(item.product_id)
        status = product.add_product2user(uid, item.product_num, const.TASK, extra)
        _msg = msg % ({'name': user.nickname or user.name, 'gift': item.title})
        data = dict(
            message=_msg,
            event_id=live_id
        )
        Xlive.send_live_msg(data, 'activity')
        return {'ret': True, 'task': task.format(uid), 'item': item.format()}

    lockkey = 'lock:task:%s:%s' % (uid, task_id)
    with util.Lockit(Redis, lockkey) as locked:
        if locked:
            return error.TaskError(u'请求频率过高')
        # 查看是否有抽奖机会
        stat = WatchLiveTask.update_left_chance(uid, task_id)
        if not stat:
            return error.TaskError(u'无抽奖机会！')

        # 从营销中心查询/请求抽奖机会
        left_chances = Marketing.query_lottery_chance(user.partner_migu['id'], task.campaign_id)
        if isinstance(left_chances, error.ApiError):
            return send_default_gift(uid, task_id, user, extra, msg)
        if left_chances <= 0:
            # 进行抽奖机会的兑换
            ret = Marketing.execute_campaign(user.partner_migu['id'], user.phone,
                                             [task.campaign_id])
            if not ret or isinstance(ret, error.ApiError):
                return send_default_gift(uid, task_id, user, extra, msg)

        # 调用营销平台进行抽奖
        prize = Marketing.draw_lottery(user.partner_migu['id'], task.campaign_id)
        if isinstance(prize, error.ApiError):
            prize = None

        if not prize:
            # 如果没有抽中奖品，发放默认奖品
            return send_default_gift(uid, task_id, user, extra, msg)

        prize_name = None
        for i in prize['extensionInfo']:
            if i['key'] == 'levelName':
                prize_name = i['value']
                break
        item = WatchLiveTaskItem.get_item_by_identity(task_id, prize_name)
        # 更新库存
        item.update_left()

        # 生成兑奖订单
        order = UserLiveOrder.create(
            user_id=uid,
            item_id=str(item._id),
            activity_id=task_id,
            activity_type=0,
            campaign_id=task.campaign_id,
            title=item.title,
            product_id=item.product_id,
            product_num=item.product_num,
            status=const.ORDER_FINISHED,
            result=json.dumps(prize)
        )
        order.save()

        # 进行物品的发放
        product = Product.get_product(item.product_id)
        status = product.add_product2user(uid, item.product_num, const.TASK, extra)

        _msg = msg % ({'name': user.nickname or user.name, 'gift': item.title})
        data = dict(
            message=_msg,
            event_id=live_id
        )
        Xlive.send_live_msg(data, 'activity')
    return {'ret': True, 'task': task.format(uid), 'item': item.format()}


@app.route('/lives/redpacket/info', methods=['GET'])
@util.jsonapi()
def live_redpacket():
    """直播间红包活动(GET)

    :uri: /lives/redpacket/info
    :param os: 平台
    :param channels: 渠道（可选）
    :param version_code: 版本号
    :param live_id: 直播间ID
    :return: {'ret': bool}
    """
    user = request.authed_user
    params = request.values
    os = params.get('os', None)
    channels = params.get('channels', None)
    version_code = int(params.get('version_code', 0))
    live_id = params.get('live_id', None)

    if not os or not version_code or not live_id:
        return error.InvalidArguments

    uid = None
    province = None
    if user:
        uid = str(user._id)
        phone = str(user.phone)

        if user.province:
            province = user.provice

        if not user.province and util.is_mobile_phone(phone):
            province = Migu.get_user_info_by_account_name(phone)
            if not isinstance(province, error.ApiError):
                user.update_model({'$set': {'province': province}})
            else:
                province = None

    live = Xlive.get_live(live_id)
    # live = Xlive.test_lives()[0]
    if not live:
        return error.LiveError('直播不存在')

    red_packet = None
    red_packet_count = 0

    # 先获取已存在的红包，以及已经参与的直播间抢红包
    _ids = UserRedPacket.user_red_packets(uid)
    #user_rps = []
    for urp in UserRedPacket.get_list(_ids):
        # 查找用户直播间抽取红包记录
        #if urp.resource_id is None:
        #    user_rps.append((urp.campaign_id, urp.resource_id))
        if not LiveRedPacket.get_one(urp.active_id):
            continue
        if urp.chance <= 0:
            continue
        if red_packet is None or red_packet.expire_at > urp.expire_at:
            red_packet = urp
        red_packet_count += urp.chance
    red_packet = red_packet.format(red_packet_count) if red_packet else red_packet
    return {'red_packet': red_packet}


@app.route('/lives/redpacket/query_new', methods=['POST', 'GET'])
@util.jsonapi()
def query_new_redpacket():
    """
    :uri: /lives/redpacket/query_new
    :param os: 平台
    :param channels: 渠道（可选）
    :param version_code: 版本号
    :param live_id: 直播间ID
    :param active_id: 活动ID
    :return:
    """
    user = request.authed_user
    params = request.values
    os = params.get('os', None)
    channels = params.get('channels', None)
    version_code = int(params.get('version_code', 0))
    live_id = params.get('live_id', None)
    active_id = params.get('active_id', None)

    if not os or not version_code or not active_id or not live_id:
        return error.InvalidArguments

    live = Xlive.get_live(live_id)
    if not live:
        return error.LiveError(u'直播不存在')

    activity = LiveRedPacket.get_one(active_id)
    if not activity:
        return error.RedPacketError(u'直播红包活动不存在！')

    uid = None
    province = None
    if user:
        uid = str(user._id)
        phone = str(user.phone)

        if user.province:
            province = user.provice

        if not user.province and util.is_mobile_phone(phone):
            province = Migu.get_user_info_by_account_name(phone)
            if not isinstance(province, error.ApiError):
                user.update_model({'$set': {'province': province}})
            else:
                province = None
    else:
        return {'red_packet': activity.format()}

    live_authors = [] if not activity.live_authors else activity.live_authors.split('\r\n')
    live_games = [] if not activity.live_games else activity.live_games.split('\r\n')
    key_words = [] if not activity.keyword else activity.keyword.split(u',')

    # 过滤主播
    if live_authors and live['user_id'] not in live_authors:
        return error.RedPacketError(u'不符合活动条件！')
    # 过滤游戏
    if live_games and live['game_id'] not in live_games:
        return error.RedPacketError(u'不符合活动条件！')
    # 过滤关键字
    if key_words and not any(map(lambda x: x in live['name'], key_words)):
        return error.RedPacketError(u'不符合活动条件！')

    if activity.os not in ['all', os]:
        return error.RedPacketError(u'不符合活动条件！')

    if (activity.version_code_mix and activity.version_code_mix > version_code) or \
            (activity.version_code_max and activity.version_code_max < version_code):
        return error.RedPacketError(u'不符合活动条件！')

    if channels and activity.channels and channels not in activity.channels:
        return error.RedPacketError(u'不符合活动条件！')

    if activity.login == 'login' and (not uid or not activity.user_in_group(str(activity.group), uid)):
        return error.RedPacketError(u'不符合活动条件！')

    if activity.province and not province:
        return error.RedPacketError(u'不符合活动条件！')

    if province and province not in activity.province:
        return error.RedPacketError(u'不符合活动条件！')

    key = 'lock:receive_red_packet:%s' % (uid)
    with util.Lockit(Redis, key) as locked:
        if locked:
            return error.RedPacketError(u'领取红包失败，请稍后再试！')

        # 查看用户是否已领取该红包
        if UserRedPacket.check_live_redpacket(uid, activity._id):
            return error.RedPacketError(u'用户已领取该红包！')

        _urp = UserRedPacket.init()
        _urp.active_id = activity._id
        _urp.campaign_id = activity.campaign_id
        _urp.chance = activity.chance
        _urp.expire_at = activity.expire_at
        _urp.user_id = uid
        _urp.source = 0     # 不可被分享
        _urp.create_model()
        return {'red_packet': _urp.format(activity.chance)}


@app.route('/lives/redpacket/grab', methods=['POST', 'GET'])
@util.jsonapi(login_required=True)
def grab_redpacket():
    """直播间红包争抢(POST)

    :uri: /lives/redpacket/grab
    :param os: 平台
    :param channels: 渠道（可选）
    :param version_code: 版本号
    :param live_id: 直播间ID
    :param source_id: 红包ID
    :return: {'ret': bool}
    """
    user = request.authed_user
    params = request.values
    os = params.get('os', None)
    channels = params.get('channels', None)
    version_code = int(params.get('version_code', 0))
    live_id = params.get('live_id', None)
    source_id = params.get('source_id', None)

    if not os or not version_code or not source_id or not live_id:
        return error.InvalidArguments

    uid = None
    province = None
    if user:
        uid = str(user._id)
        phone = str(user.phone)

        if user.province:
            province = user.provice

        if not user.province and util.is_mobile_phone(phone):
            province = Migu.get_user_info_by_account_name(phone)
            if not isinstance(province, error.ApiError):
                user.update_model({'$set': {'province': province}})
            else:
                province = None

    red_packet = UserRedPacket.get_one(source_id)
    if not red_packet:
        return error.RedPacketError(u'红包不存在！')

    activity = LiveRedPacket.get_one(red_packet.active_id)
    if not activity:
        return error.RedPacketError(u'直播红包活动不存在！')

    # 查看是否有抽奖机会
    if red_packet.chance <= 0:
        return error.RedPacketError(u'已达到领取红包次数上限！')

    def get_user_redpackets(no_share=False):
        # 先获取已存在的红包，以及已经参与的直播间抢红包
        _red_packet, _red_packet_count = None, 0
        _ids = UserRedPacket.user_red_packets(uid)
        for urp in UserRedPacket.get_list(_ids):
            if not LiveRedPacket.get_one(urp.active_id):
                continue
            if urp.source == 0:
                # 过滤掉所有直播间抽奖机会
                continue
            if urp.chance <= 0:
                continue
            if _red_packet is None or _red_packet.expire_at > urp.expire_at:
                _red_packet = urp
            _red_packet_count += 1
        # 如果是直播间红包，返回直播间红包；如果不是，返回新红包
        if red_packet.from_user == red_packet.user_id:
            _red_packet = red_packet
        # 如果没有新红包，返回当前红包，并标记剩余红包数为0
        if not _red_packet:
            _red_packet = red_packet
        return _red_packet.format(_red_packet_count, no_share)

    def send_default_gift(uid, task_id, user, extra):
        return {'ret': True, 'red_packet': get_user_redpackets(True), 'item': None}

    extra = dict(
        migu_id=user.partner_migu['id'],
        phone=user.phone,
        campaign_id=red_packet.campaign_id
    )
    item = None

    key = 'lock:receive_red_packet:%s' % (uid)
    with util.Lockit(Redis, key) as locked:
        if locked:
            return error.RedPacketError(u'领取红包失败，请稍后再试！')

        # 如果是直播间红包抽奖，则需要先调用抽奖接口再获取红包物品
        if not red_packet.source:
            # 从营销中心查询/请求抽奖机会
            left_chances = Marketing.query_lottery_chance(user.partner_migu['id'], red_packet.campaign_id)
            if isinstance(left_chances, error.ApiError):
                return send_default_gift(uid, source_id, user, extra)
            if left_chances <= 0:
                # 进行抽奖机会的兑换
                ret = Marketing.execute_campaign(user.partner_migu['id'], user.phone, [red_packet.campaign_id])
                if not ret or isinstance(ret, error.ApiError):
                    return send_default_gift(uid, source_id, user, extra)

            # 扣除用户抽奖次数
            red_packet.take_chance()

            # 调用营销平台进行抽奖
            prize = Marketing.draw_lottery(user.partner_migu['id'], red_packet.campaign_id)
            if isinstance(prize, error.ApiError):
                prize = None
            if not prize:
                # 如果没有抽中奖品，发放默认奖品
                return send_default_gift(uid, source_id, user, extra)

            # 先请求红包机会
            extra.update({'campaign_id': activity.redpacket_id})
            ret = Marketing.execute_campaign(user.partner_migu['id'], user.phone, [activity.redpacket_id])
            if not ret or isinstance(ret, error.ApiError):
                return send_default_gift(uid, source_id, user, extra)
            # 抢红包
            rps = Marketing.query_red_package_by_user(user.partner_migu['id'], activity.redpacket_id)
            if isinstance(rps, error.ApiError):
                return send_default_gift(uid, source_id, user, extra)
            if not rps:
                return send_default_gift(uid, source_id, user, extra)
            # 将最新的红包放到最前面
            rps.sort(key=lambda x: x['createDate']['time'], reverse=True)

            # 将红包放入用户可分享红包
            _urp = UserRedPacket.init()
            _urp.active_id = activity._id
            _urp.campaign_id = activity.redpacket_id
            _urp.resource_id = rps[0]['id']
            _urp.chance = 1
            _urp.expire_at = activity.share_expire_at
            _urp.item_count = activity.share_count
            _urp.user_id = uid
            _urp.from_user = uid
            _urp.source = 1
            _urp.create_model()
            red_packet = _urp

        # 从分享红包获取物品
        prize = Marketing.grab_red_package(user.partner_migu['id'], red_packet.campaign_id, red_packet.resource_id)
        if isinstance(prize, error.ApiError):
            return {'ret': False, 'red_packet': get_user_redpackets(), 'item': None}

        # 如果红包领取成功，扣除红包领取次数
        red_packet.take_chance()
        if not prize:
            # 如果没有抽中奖品，发放默认奖品
            return send_default_gift(uid, source_id, user, extra)

        # 发放物品
        prize_name = prize.get('name')
        item = LiveRedPacketItem.get_item_by_identity(activity._id, prize_name)
        # 更新库存
        item.update_left()

        # 生成兑奖订单
        order = UserLiveOrder.create(
            user_id=str(user._id),
            item_id=str(item._id),
            activity_id=str(activity._id),
            activity_type=1,
            campaign_id=red_packet.campaign_id,
            title=item.title,
            product_id=item.product_id,
            product_num=item.product_num,
            status=const.ORDER_FINISHED,
            result=json.dumps(prize)
        )
        order.save()

        # 进行物品的发放
        product = Product.get_product(item.product_id)
        product.add_product2user(uid, item.product_num, const.TASK, extra)

    return {'ret': True, 'red_packet': get_user_redpackets(), 'item': item and item.format()}


@app.route('/share/redpacket/query_new', methods=['POST', 'GET'])
@util.jsonapi(login_required=True)
def query_shared_redpacket():
    """分享红包争抢(POST)

    :uri: /share/redpacket/query_new
    :param： source_id: 红包ID
    :return: {'ret': bool}
    """
    user = request.authed_user
    params = request.values
    source_id = params.get('source_id', None)
    uid = str(user._id)

    if not source_id:
        return error.InvalidArguments

    source_rp = UserRedPacket.get_one(source_id)
    if not source_rp:
        return error.RedPacketError(u'分享红包不存在！')

    acticity = LiveRedPacket.get_one(source_rp.active_id)
    if not acticity:
        return error.RedPacketError(u'分享红包不存在！')

    if time.time() >= acticity.share_expire_at:
        return error.RedPacketError(u'不好意思，红包已经过期啦')

    # 检查红包是否还有剩余领取机会
    if source_rp.item_count < 1:
        return error.RedPacketError(u'不好意思，红包已经被抢完啦')

    # 检查用户是否已领取红包
    if UserRedPacket.check_shared_redpacket(uid, source_rp.campaign_id, source_rp.resource_id):
        return error.RedPacketError(u'已领取过该红包！')

    # 锁定分享红包ID，防止分享红包被抢次数超出限制
    key = 'lock:share_red_packet:%s' % (str(source_rp._id))
    with util.Lockit(Redis, key) as locked:
        if locked:
            return error.RedPacketError(u'领取分享红包失败，请稍后再试！')

        # 减少被分享红包可领取次数
        source_rp.take_item()

        _urp = UserRedPacket.init()
        _urp.active_id = source_rp.active_id
        _urp.campaign_id = source_rp.campaign_id
        _urp.resource_id = source_rp.resource_id
        _urp.chance = 1
        _urp.expire_at = source_rp.expire_at
        _urp.item_count = source_rp.item_count
        _urp.user_id = uid
        _urp.from_user = source_rp.from_user
        _urp.source = 1     # 不可被分享
        _urp.create_model()

    return {'ret': True}
