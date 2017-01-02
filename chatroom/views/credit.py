# -*- coding: utf8 -*-
from flask import request
from wanx import app
from wanx.base import util
from wanx.models.credit import UserCredit, UserGemLog, UserGoldLog
from wanx.models.product import UserProduct


@app.route('/credit/user', methods=['GET'])
@util.jsonapi(login_required=True)
def user_credit():
    """获取用户经济信息 (GET&LOGIN)

    :uri: /credit/user
    :return: {'gem': int, 'gold': int, 'gift_num': int}
    """
    user = request.authed_user
    uc = UserCredit.get_or_create_user_credit(user_id=str(user._id))
    uproducts = UserProduct.get_user_products(str(user._id))
    gift_num = sum([up.num for up in uproducts])
    return {'gem': uc.gem, 'gold': uc.gold, 'gift_num': gift_num}


@app.route('/credit/gem_log', methods=['GET'])
@util.jsonapi(login_required=True)
def user_gem_log():
    """获取用户游票交易记录 (GET&LOGIN)

    :uri: /credit/gem_log
    :param page: 页码
    :param nbr: 每页数量
    :return: {'logs': list, 'end_page': bool}
    """
    user = request.authed_user
    page = int(request.values.get('page', 1))
    pagesize = int(request.values.get('nbr', 10))

    logs = UserGemLog.get_user_logs(str(user._id), page, pagesize)
    logs = [log.format() for log in logs]
    return {'logs': logs, 'end_page': len(logs) != pagesize}


@app.route('/credit/gold_log', methods=['GET'])
@util.jsonapi(login_required=True)
def user_gold_log():
    """获取用户游米交易记录 (GET&LOGIN)

    :uri: /credit/gold_log
    :param page: 页码
    :param nbr: 每页数量
    :return: {'logs': list, 'end_page': bool}
    """
    user = request.authed_user
    page = int(request.values.get('page', 1))
    pagesize = int(request.values.get('nbr', 10))

    logs = UserGoldLog.get_user_logs(str(user._id), page, pagesize)
    logs = [log.format() for log in logs]
    return {'logs': logs, 'end_page': len(logs) != pagesize}
