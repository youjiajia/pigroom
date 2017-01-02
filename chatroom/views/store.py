# -*- coding: utf8 -*-
from flask import request
from wanx import app
from wanx.base import util, error, const
from wanx.base.xredis import Redis
from wanx.platforms.migu import Marketing
from wanx.models.store import Store, StoreItem, UserOrder, UserOrderAddress
from wanx.models.credit import UserCredit
from wanx.models.product import (Product, PHYSICAL_OBJECT, MOBILE_TRAFFIC,
                                 UNICOM_TRAFFIC, TELECOM_TRAFFIC)

import json


@app.route('/store/all_exchanges', methods=['GET'])
@util.jsonapi()
def all_exchanges():
    """获取兑换商品活动列表(GET)

    :uri: /store/all_exchanges
    :return: {'stores': <Store>list}
    """
    stores = Store.get_exchanges()
    exchanges = []
    for store in stores:
        items = [item.format() for item in StoreItem.get_store_items(store.store_id)]
        tmp = store.format()
        tmp['items'] = items
        exchanges.append(tmp)

    return {'stores': exchanges}


@app.route('/store/all_lotteries', methods=['GET'])
@util.jsonapi()
def lotteries():
    """获取抽奖活动列表(GET)

    :uri: /store/all_lotteries
    :return: {'stores': <Store>list}
    """
    stores = Store.get_lotteries()
    lotteries = [store.format() for store in stores]
    return {'stores': lotteries}


@app.route('/store/lottery_info', methods=['GET'])
@util.jsonapi()
def lottery_info():
    """获取抽奖活动详细信息(GET)

    :uri: /store/lottery_info
    :param store_id: 兑换活动ID
    :return: {'lottery': <Store>object}
    """
    user = request.authed_user
    store_id = request.values.get('store_id', None)
    if not store_id:
        return error.InvalidArguments

    store = Store.get_store(store_id)
    if not store or not store.online():
        return error.StoreError('该抽奖活动不存在或已下线')

    if store.pause():
        return error.StoreError('该抽奖活动还未开始')

    lottery = store.format()
    items = [item.format() for item in StoreItem.get_store_items(store.store_id)]
    lottery['items'] = items
    chances = 0
    if user:
        chances = Marketing.query_lottery_chance(user.partner_migu['id'], store.campaign_id)
        if isinstance(chances, error.ApiError):
            return chances

    lottery['chances'] = chances
    return {'lottery': lottery}


@app.route('/store/exchange_product', methods=['POST'])
@util.jsonapi(login_required=True)
def exchange_product():
    """兑换物品接口(POST&LOGIN)

    :uri: /store/exchange_product
    :param store_id: 兑换活动ID
    :param item_id: 兑换物品ID
    :return: {'item': <Item>object, 'order': <Order>object}
    """
    user = request.authed_user
    store_id = request.values.get('store_id', None)
    item_id = request.values.get('item_id', None)

    user_ip = request.remote_addr
    device = request.values.get('device', None)

    if not store_id or not item_id:
        return error.InvalidArguments

    store = Store.get_store(store_id)
    if not store or not store.online():
        return error.StoreError('该兑换活动不存在或已下线')

    item = StoreItem.get_store_item(store_id, item_id)
    if not item:
        return error.StoreError('该兑换奖品不存在')

    # 库存判断
    if item.left_num < 1:
        return error.StoreError('该兑换奖品已卖完')

    product = Product.get_product(item.product_id)

    # 判断手机号
    if product.product_type == MOBILE_TRAFFIC and not util.is_mobile_phone(user.phone):
        return error.StoreError('非移动手机号不能兑换此商品')

    if product.product_type == UNICOM_TRAFFIC and not util.is_unicom_phone(user.phone):
        return error.StoreError('非联通手机号不能兑换此商品')

    if product.product_type == TELECOM_TRAFFIC and not util.is_telecom_phone(user.phone):
        return error.StoreError('非电信手机号不能兑换此商品')

    uc = UserCredit.get_or_create_user_credit(user_id=str(user._id))
    if item.credit_type == const.SALE_GEM and uc.gem < item.credit_value:
        return error.StoreError('你的游票不足，无法兑换此物品哦！')
    elif item.credit_type == const.SALE_GOLD and uc.gold < item.credit_value:
        return error.StoreError('你的游米不足，无法兑换此物品哦！')

    key = 'lock:store:%s' % (str(user._id))
    status = None
    with util.Lockit(Redis, key) as locked:
        if locked:
            return error.StoreError('兑换太频繁')

        extra = dict(
            migu_id=user.partner_migu['id'],
            phone=user.phone,
            campaign_id=store.resource_campaign_id
        )
        status = product.add_product2user(str(user._id), item.product_num, const.EXCHANGE, extra)
        if status == const.ORDER_FAILED:
            return error.StoreError('兑换失败')
        else:
            # 扣除货币
            if item.credit_type == const.SALE_GEM:
                uc.reduce_gem(item.credit_value, const.EXCHANGE)
            elif item.credit_type == const.SALE_GOLD:
                uc.reduce_gold(item.credit_value, const.EXCHANGE)

    # 更新库存
    item.left_num -= 1
    item.use_num += 1
    item.save()
    # 记录订单
    order = UserOrder.create(
        user_id=str(user._id),
        item_id=item.item_id,
        store_id=item.store_id,
        store_type=store.store_type,
        campaign_id=store.campaign_id,
        title=item.title,
        product_id=item.product_id,
        product_num=item.product_num,
        status=status,
    )

    # 营销数据入库经分  兑换活动
    data_dict = dict(
        cmd="exchange",
        opt="1",
        deviceid=request.values.get('device', ''),
        mobile=user.phone,
        source=request.values.get('source', 'activity'),
        activityid=store_id,
        activityname=store.title
    )
    Marketing.jf_report(data_dict)

    return {'item': item.format(), 'order': order.format()}


@app.route('/store/draw_lottery', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def draw_lottery():
    """抽奖接口(POST&LOGIN)

    :uri: /store/draw_lottery
    :param store_id: 抽奖活动ID
    :return: {'item': <Item>object, 'order': <Order>object}
    """
    user = request.authed_user
    store_id = request.values.get('store_id', None)

    user_ip = request.remote_addr
    device = request.values.get('device', None)

    if not store_id:
        return error.InvalidArguments

    store = Store.get_store(store_id)
    if not store or not store.online():
        return error.StoreError('该抽奖活动不存在或已下线')

    if store.pause():
        return error.StoreError('该抽奖活动还未开始')

    # 进行抽奖奖项库存判断
    items = StoreItem.get_store_items(store_id)
    left_num = sum(map(lambda x: x.left_num, items))
    if left_num < 0:
        return error.StoreError('该抽奖活动奖项已被领取完')

    # 判断号码是否符合规则
    info = Marketing.query_campaign(store.campaign_id)
    if isinstance(info, error.ApiError):
        return info
    if info['mobile_phone_only'] and not util.is_mobile_phone(user.phone):
        return error.StoreError('该抽奖活动只对移动手机号开放')

    # 查看是否有抽奖机会
    left_chances = Marketing.query_lottery_chance(user.partner_migu['id'], store.campaign_id)
    if isinstance(left_chances, error.ApiError):
        return error.StoreError('获取抽奖机会失败')

    if left_chances <= 0:
        uc = UserCredit.get_or_create_user_credit(user_id=str(user._id))
        if store.credit_type == const.SALE_GEM and uc.gem < store.credit_value:
            return error.StoreError('你的游票不足，无法参与抽奖哦！')
        elif store.credit_type == const.SALE_GOLD and uc.gold < store.credit_value:
            return error.StoreError('你的游米不足，无法参与抽奖哦！')

        key = 'lock:store:%s' % (str(user._id))
        with util.Lockit(Redis, key) as locked:
            if locked:
                return error.StoreError('抽奖太频繁')

            # 进行抽奖机会的兑换
            ret = Marketing.execute_campaign(user.partner_migu['id'], user.phone,
                                             [store.campaign_id])
            if not ret or isinstance(ret, error.ApiError):
                return error.StoreError('兑换抽奖机会失败')
            else:  # 扣除货币
                if store.credit_type == const.SALE_GEM:
                    uc.reduce_gem(store.credit_value, const.LOTTERY_REWAED)
                elif store.credit_type == const.SALE_GOLD:
                    uc.reduce_gold(store.credit_value, const.LOTTERY_REWAED)

    # 调用营销平台进行抽奖
    prize = Marketing.draw_lottery(user.partner_migu['id'], store.campaign_id)
    if isinstance(prize, error.ApiError):
        return prize

    # 营销数据入库经分  抽奖活动
    data_dict = dict(
        cmd="lottery",
        opt="1",
        deviceid=request.values.get('device', ''),
        mobile=user.phone,
        source=request.values.get('source', 'activity'),
        activityid=store_id,
        activityname=store.title
    )
    Marketing.jf_report(data_dict)
    # 营销平台奖项有各种限制, 会导致用户抽不中任何物品的可能。
    # 比如有A/B/C三个抽奖奖项，概率分别为20%/30%/50%，如果A物品配置为一个手机号只能中一次，
    # 那当用户抽中过A之后，以后再抽奖，就会有20%(A)的几率啥也抽不中。如果B物品库存又没有了，
    # 那用户就会有20%(A)+30%(B)的几率啥也抽不中。为了处理这种情况，目前默认如果抽不中就给
    # 用户发一个抽奖活动配置的"default"奖项(运营后台: 营销平台奖项ID配置为'default')
    if not prize:
        item = StoreItem.get_item_by_identity(store.store_id, 'default')
        if not item:
            return {'item': None, 'order': None}
        else:
            # 更新库存
            item.left_num -= 1
            item.use_num += 1
            item.save()
            # 生成兑奖订单
            order = UserOrder.create(
                user_id=str(user._id),
                item_id=item.item_id,
                store_id=item.store_id,
                store_type=store.store_type,
                campaign_id=store.campaign_id,
                title=item.title,
                product_id=item.product_id,
                product_num=item.product_num,
                status=const.ORDER_NEED_DRAW,
                result=''
            )
            extra = dict(
                migu_id=user.partner_migu['id'],
                phone=user.phone,
                campaign_id=store.resource_campaign_id
            )
            # 进行物品的发放
            product = Product.get_product(item.product_id)
            status = product.add_product2user(str(user._id), item.product_num, const.LOTTERY, extra)

            # 订单状态更新
            if status != order.status:
                order.status = status
                order.save()

            return {'item': item.format(), 'order': order.format()}

    # 由于营销平台看不到id, 暂时只能用奖项名称进行对应
    prize_name = None
    for i in prize['extensionInfo']:
        if i['key'] == 'levelName':
            prize_name = i['value']
            break

    item = StoreItem.get_item_by_identity(store.store_id, prize_name)
    # 更新库存
    item.left_num -= 1
    item.use_num += 1
    item.save()

    # 无领取规则的活动营销平台会自动领取
    status = const.ORDER_NEED_DRAW if info['is_exchange_rule'] else const.ORDER_IN_HAND
    # 生成兑奖订单
    order = UserOrder.create(
        user_id=str(user._id),
        item_id=item.item_id,
        store_id=item.store_id,
        store_type=store.store_type,
        campaign_id=store.campaign_id,
        title=item.title,
        product_id=item.product_id,
        product_num=item.product_num,
        status=status,
        result=json.dumps(prize),
    )

    product = Product.get_product(item.product_id)
    if product.product_type != PHYSICAL_OBJECT:  # 非实物物品直接去营销平台进行奖励兑换
        # 有领取规则的抽奖活动的非实物物品自动领取, 无领取规则的活动营销平台会自动领取
        if info['is_exchange_rule']:
            # 获取用户可兑换奖励信息
            prizes = Marketing.query_exchengable_prizes(user.partner_migu['id'],
                                                        order.campaign_id)
            if isinstance(prizes, error.ApiError):
                return prizes

            # 进行奖励的兑换, 目前最后一条为最近获得的奖励
            for _prize in prizes[::-1]:
                exchenge_ids = map(lambda x: x['id'], _prize['exchengeResources'])
                exchengeable_id = _prize['exchengableResource']['id']
                if [prize['id']] == exchenge_ids:
                    exchenge_ids = [prize['id']]
                    ret = Marketing.draw_exchengable_prize(user.partner_migu['id'],
                                                           order.campaign_id,
                                                           exchenge_ids, exchengeable_id,
                                                           prize['amount'])

                    if isinstance(ret, error.ApiError):
                        return ret

        # 由于对方没有返回订单ID, 只能通过获取用户最近一个已兑换奖励的订单ID, 实物物品需要手动领取
        ret, _ = Marketing.query_exchenged_prizes(user.partner_migu['id'], order.campaign_id,
                                                  page=1, pagesize=1)
        if isinstance(ret, error.ApiError):
            return ret

        # 更新订单信息
        if isinstance(ret, list) and len(ret) > 0 and 'recId' in ret[0]:
            order.recid = ret[0]['recId']

        order.status = const.ORDER_IN_HAND
        order.save()

        extra = dict(
            migu_id=user.partner_migu['id'],
            phone=user.phone,
            campaign_id=store.resource_campaign_id
        )
        # 进行物品的发放
        status = product.add_product2user(str(user._id), item.product_num, const.LOTTERY, extra)

        # 订单状态更新
        if status != order.status:
            order.status = status
            order.save()

    return {'item': item.format(), 'order': order.format()}


@app.route('/store/receive_order', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def receive_order():
    """领取订单奖励(POST&LOGIN)

    :uri: /store/receive_order
    :param order_id: 订单ID
    :param name: 真实名字 (实物物品)
    :param id_card: 身份证 (实物物品)
    :param address: 地址 (实物物品)
    :return: {'order': <Order>object}
    """
    user = request.authed_user
    order_id = request.values.get('order_id', None)
    name = request.values.get('name', None)
    id_card = request.values.get('id_card', None)
    address = request.values.get('address')

    if not order_id:
        return error.InvalidArguments

    order = UserOrder.get_order(order_id)
    if not order or order.user_id != str(user._id):
        return error.StoreError('用户订单不存在')

    if order.status != const.ORDER_NEED_DRAW:
        return error.StoreError('用户订单状态错误')

    store = Store.get_store(order.store_id)
    if not store or not store.online():
        return error.StoreError('该抽奖活动不存在或已下线')

    product = Product.get_product(order.product_id)
    if product.product_type == PHYSICAL_OBJECT:  # 实物物品
        if not name or not id_card or not address:
            return error.InvalidArguments

        addr = UserOrderAddress.create(
            order_id=order_id,
            user_id=str(user._id),
            name=name,
            phone=user.phone,
            id_card=id_card,
            address=address
        )

    prize = json.loads(order.result)

    # 获取用户可兑换奖励信息
    exchenge_prizes = Marketing.query_exchengable_prizes(user.partner_migu['id'], order.campaign_id)
    if isinstance(exchenge_prizes, error.ApiError):
        return exchenge_prizes

    for _prize in exchenge_prizes:
        exchenge_ids = map(lambda x: x['id'], _prize['exchengeResources'])
        exchengeable_id = _prize['exchengableResource']['id']

        if [prize['id']] == exchenge_ids:
            exchenge_ids = [prize['id']]
            if product.product_type == PHYSICAL_OBJECT:  # 实物物品
                ret = Marketing.draw_exchengable_prize(user.partner_migu['id'], order.campaign_id,
                                                       exchenge_ids, exchengeable_id,
                                                       prize['amount'], addr.name, addr.phone,
                                                       addr.address, addr.id_card)
            else:
                ret = Marketing.draw_exchengable_prize(user.partner_migu['id'], order.campaign_id,
                                                       exchenge_ids, exchengeable_id,
                                                       prize['amount'])

            if isinstance(exchenge_prizes, error.ApiError):
                return ret

    # 由于对方没有返回订单ID, 只能通过获取用户最近一个已兑换奖励的订单ID
    ret, _ = Marketing.query_exchenged_prizes(user.partner_migu['id'], order.campaign_id,
                                              page=1, pagesize=1)
    if isinstance(ret, error.ApiError):
        return ret

    # 更新订单信息
    if isinstance(ret, list) and len(ret) > 0 and 'recId' in ret[0]:
        order.recid = ret[0]['recId']

    order.status = const.ORDER_IN_HAND
    order.save()

    extra = dict(
        migu_id=user.partner_migu['id'],
        phone=user.phone,
        campaign_id=store.resource_campaign_id
    )
    # 进行物品的发放
    status = product.add_product2user(str(user._id), order.product_num, const.LOTTERY, extra)

    # 订单状态更新
    if status != order.status:
        order.status = status
        order.save()

    return {'order': order.format()}


@app.route('/store/user_orders', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def user_orders():
    """获取用户活动订单信息(POST&LOGIN)

    :uri: /store/user_orders
    :param store_id: 商店ID
    :param page: 页码
    :param nbr: 每页数量
    :return: {'orders': <Order>list, 'end_page': bool}
    """
    user = request.authed_user
    store_id = request.values.get('store_id', None)
    page = int(request.values.get('page', 1))
    pagesize = int(request.values.get('nbr', 10))

    if not store_id:
        return error.InvalidArguments

    store = Store.get_store(store_id)
    if not store or not store.online():
        return error.StoreError('该抽奖活动不存在或已下线')

    # 获得游玩发放物品的订单
    orders = UserOrder.get_user_store_orders(str(user._id), store_id, page, pagesize)
    orders = [order.format() for order in orders]
    return {'orders': orders, 'end_page': len(orders) != pagesize}


@app.route('/store/gift_codes', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def gift_codes():
    """获取礼包类物品的奖励信息(POST&LOGIN)

    :uri: /store/gift_codes
    :param store_id: 商店ID
    :param rid: 抽奖奖项ID
    :return: {'codes': <code>list}
    """
    user = request.authed_user
    store_id = request.values.get('store_id', None)
    rid = request.values.get('rid', None)

    if not store_id or not rid:
        return error.InvalidArguments

    store = Store.get_store(store_id)
    if not store or not store.online():
        return error.StoreError('该抽奖活动不存在或已下线')

    # 获取抽奖对应奖项的所有获奖记录
    codes = []
    page = 1
    end_page = False
    while not end_page:
        orders, end_page = Marketing.query_exchenged_prizes(str(user.partner_migu['id']),
                                                            store.campaign_id,
                                                            page=page, pagesize=50)
        # 过滤奖项ID对应的兑换记录
        for order in orders:
            consume_ids = [str(res['resourceId']) for res in order['consumeResources']]
            if [str(rid)] == consume_ids:
                codes.append({
                    'name': order['exchengedResouce']['name'],
                    'code': order['exchangeCode'],
                    'create_at': int(order['exchangeTime']['time']) / 1000
                })

        page += 1

    return {'codes': codes}
