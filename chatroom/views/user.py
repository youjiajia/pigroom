# -*- coding: utf8 -*-
from bson.binary import Binary
from bson.objectid import ObjectId
from flask import request

from wanx.base.spam import Spam
from wanx.base.xredis import Redis
from wanx.base.xpinyin import Pinyin
from wanx.models.user import User, FriendShip, UserShare
from wanx.models.game import Game, UserSubGame
from wanx.models.credit import UserCredit
from wanx.models.product import UserProduct
from wanx.models.task import UserTask, FOLLOW_USER, SHARE_VIDEO
from wanx.platforms import ChargeSDK, WeiXin, QQ, SMS, Migu, Xlive
from wanx import app
from wanx.base import error, const, util

import os
import random
import time
import uuid
import datetime


@app.route('/users/refresh_token', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def refresh_token():
    """刷新用户token时间 (GET|POST&LOGIN)

    :uri: /users/refresh_token
    :returns: {'user': Object}
    """
    ut = request.values.get("ut", None)
    user = request.authed_user
    token = User.set_token(ut, str(user._id))
    if token:
        User.recommend_users(str(user._id))
        # 更新用户活跃时间
        user.update_model({'$set': {'update_at': time.time()}})
    # 初始化用户任务
    UserTask.create_and_init_user_tasks(str(user._id))

    return {'user': user.format()}


@app.route('/users/<string:uid>', methods=['GET'])
@util.jsonapi()
def get_user(uid):
    """获取用户详细信息 (GET)

    :uri: /users/<string:uid>
    :returns: object
    """
    user = User.get_one(uid)
    if not user:
        return error.UserNotExist

    user_lives = Xlive.get_user_lives(uid)
    live_ids = [ul['event_id'] for ul in user_lives]

    user_info = user.format()
    user_info.update({'live_id': live_ids[0] if live_ids else ''})

    # 如果是登录用户自己返回货币信息
    if request.authed_user and str(request.authed_user._id) == uid:
        uc = UserCredit.get_or_create_user_credit(user_id=uid)
        uproducts = UserProduct.get_user_products(str(uid))
        gift_num = sum([up.num for up in uproducts])
        user_info.update({'gem': uc.gem, 'gold': uc.gold, 'gift_num': gift_num})

    return user_info


@app.route("/users/register", methods=("POST", "GET",))
@util.jsonapi()
def register():
    """用户注册 (GET|POST)

    :uri: /users/register
    :param name: 用户名
    :param password: 密码
    :param nickname: 昵称
    :returns: {'user': object, 'ut': string}
    """
    params = request.values.to_dict()
    name = params.get("name", None)
    # delete password from data so that we don't save it to mongo
    password = str(params.pop("password", None))
    nickname = params.get('nickname', None)
    if not name or not password or not nickname:
        return error.InvalidArguments

    invalid_error = User.invalid_password(password)
    if invalid_error:
        return invalid_error

    invalid_error = User.invalid_nickname(nickname)
    if invalid_error:
        return invalid_error

    if User.get_by_name(name):
        return error.UserExists

    user = User.init()
    user.update(params)

    salt = os.urandom(const.PWD_HASH_LEN)
    pwd = User.gen_pwd_hash(password, salt)
    user._salt = Binary(salt)
    user._password = Binary(pwd)
    uid = user.create_model()
    new_user = User.get_one(uid)

    # 初始化用户任务
    UserTask.create_and_init_user_tasks(str(new_user._id))

    token = User.gen_token(str(uid))
    return {'user': new_user.format(), 'ut': token}


@app.route("/users/sms_code", methods=("POST", "GET"))
@util.jsonapi()
def send_phone_code():
    """发送短信验证码 (GET|POST)

    :uri: /users/sms_code
    :param phone: 手机号
    :param action: 触发动作(可选)(注册:reg)
    :returns: {}
    """
    params = request.values
    phone = params.get('phone', None)
    action = params.get('action', None)
    if not phone:
        return error.InvalidArguments
    # 如果是注册验证码,提前判断手机号是否已存在
    if action == 'reg' and User.get_by_phone(phone):
        return error.UserExists

    ret = SMS.send_code(phone)
    if not ret:
        return error.SendCodeFailed
    return {}


@app.route("/users/verify_sms_code", methods=("POST", "GET"))
@util.jsonapi()
def verify_sms_code():
    """验证短信验证码 (GET|POST)

    :uri: /users/verify_sms_code
    :param phone: 手机号
    :param code: 验证码
    :returns: {}
    """
    params = request.values
    phone = params.get('phone', None)
    code = params.get('code', None)

    if not phone or not code:
        return error.InvalidArguments

    if not SMS.verify_code(phone, code):
        return error.VerifyCodeFailed

    return {}


@app.route("/users/verify_phone", methods=("POST", "GET"))
@util.jsonapi()
def verify_phone():
    """验证手机号 (GET|POST)

    :uri: /users/verify_phone
    :param phone: 手机号
    :returns: {}
    """
    params = request.values
    phone = params.get('phone', None)

    if User.get_by_phone(phone):
        return error.UserExists('手机号已被注册')

    return {}


@app.route("/users/verify_nickname", methods=("POST", "GET"))
@util.jsonapi()
def verify_nickname():
    """验证昵称 (GET|POST)

    :uri: /users/verify_nickname
    :param nickname: 昵称
    :returns: {}
    """
    params = request.values
    nickname = params.get('nickname', None)

    invalid_error = User.invalid_nickname(nickname)
    if invalid_error:
        return invalid_error

    return {}


@app.route("/users/register_phone", methods=("POST", "GET",))
@util.jsonapi()
def register_phone():
    """用户手机注册 (GET|POST)

    :uri: /users/register_phone
    :param phone: 手机号
    :param password: 密码
    :param nickname: 昵称
    :param code: 短信验证码
    :param gender: 性别(可选)(1:男, 2:女)
    :returns: {'user': object, 'ut': string}
    """
    params = request.values
    phone = params.get('phone', None)
    code = params.get('code', None)
    password = params.get("password", None)
    nickname = params.get("nickname", None)
    gender = params.get("gender", 0)
    if not phone or not code or not password or not nickname:
        return error.InvalidArguments

    invalid_error = User.invalid_password(password)
    if invalid_error:
        return invalid_error

    invalid_error = User.invalid_nickname(nickname)
    if invalid_error:
        return invalid_error

    if User.get_by_phone(phone):
        return error.UserExists

    if not SMS.verify_code(phone, code):
        return error.VerifyCodeFailed

    user = User.init()
    name = '$mb$%s%s' % (phone[-4:], random.randint(1000, 9999))
    user.name = name
    user.phone = phone
    user.nickname = nickname
    user.gender = gender

    salt = os.urandom(const.PWD_HASH_LEN)
    pwd = User.gen_pwd_hash(password, salt)
    user._salt = Binary(salt)
    user._password = Binary(pwd)
    uid = user.create_model()
    new_user = User.get_one(uid)
    token = User.gen_token(str(uid))
    return {'user': new_user.format(), 'ut': token}


@app.route("/users/reset_password", methods=("POST", "GET",))
@util.jsonapi()
def reset_password():
    """重置密码 (GET|POST)

    :uri: /users/reset_password
    :param phone: 手机号
    :param password: 密码
    :param code: 短信验证码
    :returns: {}
    """
    params = request.values
    phone = params.get('phone', None)
    code = params.get('code', None)
    password = params.get("password", None)
    if not phone or not code or not password:
        return error.InvalidArguments

    invalid_error = User.invalid_password(password)
    if invalid_error:
        return invalid_error

    user = User.get_by_phone(phone)
    if not user:
        return error.UserNotExist

    if not SMS.verify_code(phone, code):
        return error.VerifyCodeFailed

    User.change_pwd(user, password)
    return {}


@app.route("/users/login", methods=("POST", "GET",))
@util.jsonapi()
def login():
    """用户登录 (GET|POST)

    :uri: /users/login
    :param name: 用户名
    :param password: 密码
    :param type: 登陆类型(name, phone,)
    :returns: {'user': object, 'ut': string}
    """
    params = request.values
    login_type = params.get('type', 'name')
    name = params.get("name", None)
    password = params.get("password", None)
    if name is None or password is None or login_type not in ['name', 'phone']:
        return error.InvalidArguments

    user = User.login(name, password, login_type=login_type)
    if not user:
        return error.LoginFailed

    # 初始化用户任务
    UserTask.create_and_init_user_tasks(str(user._id))

    token = User.gen_token(str(user._id))
    return {'user': user.format(), 'ut': token}


@app.route("/partner/users/login", methods=("POST", "GET",))
@util.jsonapi()
def partner_login():
    """第三方平台token登录 (GET|POST)

    :uri: /partner/users/login
    :param platform: 平台标识{'csdk':付费SDK, 'weixin':微信, 'qq':QQ, 'migu':咪咕}
    :param token: 用户平台token | 咪咕密码
    :param openid: 用户平台id | 咪咕手机号
    :returns: {'user': object, 'ut': string}
    """
    params = request.values
    platform = params.get('platform', None)
    token = params.get("token", None)
    openid = params.get("openid", None)
    if not token or not openid or platform not in const.PARTNER:
        return error.InvalidArguments

    if platform == 'migu':
        migu_uid = Migu.get_identityid(openid, token, const.CENTER_ACCOUNT_PHONE)
        if isinstance(migu_uid, error.ApiError):
            return migu_uid

        # 进行用户绑定
        user = User.get_platform_user('migu', migu_uid)
        if not user:
            user = User.get_by_phone(openid)
            if user:
                info = dict(
                    partner_migu={'id': migu_uid},
                    name='$mg$%s%s' % (migu_uid[-4:], random.randint(1000, 9999))
                )
                user = user.update_model({'$set': info})
            else:
                info = dict(
                    phone=openid,
                    nickname=u'咪咕用户%s%s' % (migu_uid[-4:], random.randint(1000, 9999)),
                    name='$mg$%s%s' % (migu_uid[-4:], random.randint(1000, 9999))
                )
                user = User.create_platform_user('migu', migu_uid, data=info)
        else:
            # 如果用户没有绑定手机并且手机号没有被绑定, 则自动进行手机号绑定
            if not user.phone and not User.get_by_phone(openid):
                info = dict(phone=openid)
                user = user.update_model({'$set': info})
        # 同步咪咕用户名密码
        if user:
            User.change_pwd(user, token)
    else:
        # 判断平台用户是否已经用户系统中存在
        user = User.get_platform_user(platform, openid)
        first_login = not user

        info = {}
        if platform == 'csdk':
            info = ChargeSDK(token).get_open_info()
        elif platform == 'weixin':
            info = WeiXin(token, openid).get_open_info(first_login)
        elif platform == 'qq':
            info = QQ(token, openid).get_open_info(first_login)

        if not info:
            return error.LoginFailed

        # 如果平台用户在用户系统中不存在, 则创建, 通过平台ID(openid)进行关联
        if first_login:
            open_id = info.pop('openid')
            user = User.create_platform_user(platform, open_id, data=info)
            # 给咪咕平台发送请求进行咪咕账号注册并登录绑定
            try:
                if platform in ['qq', 'weixin'] and user:
                    password = 'migu%s' % (openid[-4:])
                    ret = Migu.center_register(open_id, password, const.CENTER_ACCOUNT_INDIV)
                    if not isinstance(ret, error.ApiError):
                        openid = Migu.get_identityid(open_id, password, const.CENTER_ACCOUNT_INDIV)
                        if not isinstance(openid, error.ApiError):
                            if not User.get_platform_user('migu', openid):
                                info = {'partner_migu': {'id': openid}}
                                user.update_model({'$set': info})
            except:
                pass

    if not user:
        return error.LoginFailed

    ut = User.gen_token(str(user._id))
    return {'user': user.format(), 'ut': ut}


@app.route("/platform/users/login", methods=("POST", "GET",))
@util.jsonapi()
def platform_login():
    """第三方平台token登录 (GET|POST)

    :uri: /platform/users/login
    :param platform: 平台标识{'csdk':付费SDK, 'weixin':微信, 'qq':QQ, 'migu':咪咕}
    :param token: 用户平台token
    :returns: {'user': object, 'ut': string}
    """
    params = request.values
    platform = params.get('platform', None)
    token = params.get("token", None)
    if not token or platform not in const.PARTNER:
        return error.InvalidArguments

    t = datetime.datetime.now().microsecond
    systemtime = time.strftime('%Y%m%d%H%M%S') + str(t)[:3]

    msgid = str(uuid.uuid1())

    data = Migu.get_identity_token(token, const.CENTER_ACCOUNT_PHONE,
                                   systemtime,
                                   msgid, const.CENTER_ACCOUNT_SOURCEID,
                                   const.CENTER_ACCOUNT_APPID)
    if isinstance(data, error.ApiError):
        return data

    openid = data.get('msisdn', None)
    migu_uid = Migu.get_user_info_by_account_name(openid, keyword='identityID')
    if isinstance(migu_uid, error.ApiError):
        return migu_uid

    if platform == 'migu':
        # 进行用户绑定
        user = User.get_platform_user('migu', migu_uid)
        if not user:
            user = User.get_by_phone(openid)
            if user:
                info = dict(
                    partner_migu={'id': migu_uid},
                    name='$mg$%s%s' % (migu_uid[-4:], random.randint(1000, 9999))
                )
                user = user.update_model({'$set': info})
            else:
                info = dict(
                    phone=openid,
                    nickname=u'咪咕用户%s%s' % (migu_uid[-4:], random.randint(1000, 9999)),
                    name='$mg$%s%s' % (migu_uid[-4:], random.randint(1000, 9999))
                )
                user = User.create_platform_user('migu', migu_uid, data=info)
        else:
            # 如果用户没有绑定手机并且手机号没有被绑定, 则自动进行手机号绑定
            if not user.phone and not User.get_by_phone(openid):
                info = dict(phone=openid)
                user = user.update_model({'$set': info})
        # 同步咪咕用户名密码
        if user:
            User.change_pwd(user, token)
    else:
        # 判断平台用户是否已经用户系统中存在
        user = User.get_platform_user(platform, openid)
        first_login = not user

        info = {}
        if platform == 'csdk':
            info = ChargeSDK(token).get_open_info()
        elif platform == 'weixin':
            info = WeiXin(token, openid).get_open_info(first_login)
        elif platform == 'qq':
            info = QQ(token, openid).get_open_info(first_login)

        if not info:
            return error.LoginFailed

        # 如果平台用户在用户系统中不存在, 则创建, 通过平台ID(openid)进行关联
        if first_login:
            open_id = info.pop('openid')
            user = User.create_platform_user(platform, open_id, data=info)
            # 给咪咕平台发送请求进行咪咕账号注册并登录绑定
            try:
                if platform in ['qq', 'weixin'] and user:
                    password = 'migu%s' % (openid[-4:])
                    ret = Migu.center_register(open_id, password, const.CENTER_ACCOUNT_INDIV)
                    if not isinstance(ret, error.ApiError):
                        openid = Migu.get_identityid(open_id, password, const.CENTER_ACCOUNT_INDIV)
                        if not isinstance(openid, error.ApiError):
                            if not User.get_platform_user('migu', openid):
                                info = {'partner_migu': {'id': openid}}
                                user.update_model({'$set': info})
            except:
                pass

    if not user:
        return error.LoginFailed

    ut = User.gen_token(str(user._id))
    return {'user': user.format(), 'ut': ut}


@app.route('/users/binding', methods=('POST', 'GET'))
@util.jsonapi(login_required=True)
def binding():
    """用户绑定 (GET|POST&LOGIN)

    :uri: /users/binding
    :param platform: 平台标识 (phone, weixin, qq)
    :param openid: 平台id/手机号
    :param token: 用户平台token/短信验证码
    :returns: {}
    """
    user = request.authed_user
    params = request.values
    platform = params.get('platform', None)
    openid = params.get('openid', None)
    token = params.get('token', None)

    if platform == 'phone':
        if not SMS.verify_code(openid, token):
            return error.VerifyCodeFailed
        # 用户已经存在
        if User.get_by_phone(openid):
            return error.UserExists
        info = {'phone': openid}
        user.update_model({'$set': info})
    elif platform == 'weixin':
        # 用户已经存在
        if User.get_platform_user(platform, openid):
            return error.UserExists
        if not WeiXin(token, openid).get_open_info():
            return error.LoginFailed
        key = 'partner_%s' % (platform)
        info = {key: {'id': openid}}
        user.update_model({'$set': info})
    elif platform == 'qq':
        # 用户已经存在
        if User.get_platform_user(platform, openid):
            return error.UserExists
        if not QQ(token, openid).get_open_info():
            return error.LoginFailed
        key = 'partner_%s' % (platform)
        info = {key: {'id': openid}}
        user.update_model({'$set': info})

    return {}


@app.route('/users/unbinding', methods=('POST', 'GET'))
@util.jsonapi(login_required=True)
def unbinding():
    """用户解绑定 (GET|POST&LOGIN)

    :uri: /users/binding
    :param platform: 平台标识 (phone, weixin, qq)
    :param openid: 平台id/手机号
    :param token: 用户平台token/短信验证码
    :returns: {}
    """
    user = request.authed_user
    params = request.values
    platform = params.get('platform', None)
    openid = params.get('openid', None)
    token = params.get('token', None)

    if platform == 'phone':
        if not SMS.verify_code(openid, token):
            return error.VerifyCodeFailed
        info = {'phone': ''}
        user.update_model({'$set': info})
    elif platform == 'weixin':
        if not WeiXin(token, openid).get_open_info():
            return error.LoginFailed
        key = 'partner_%s' % (platform)
        info = {key: 1}
        user.update_model({'un$set': info})
    elif platform == 'qq':
        if not QQ(token, openid).get_open_info():
            return error.LoginFailed
        key = 'partner_%s' % (platform)
        info = {key: 1}
        user.update_model({'$unset': info})

    return {}


# TODO: being delete uid param
@app.route('/users/<string:uid>/change-password', methods=('POST', 'GET'))
@util.jsonapi(login_required=True)
def change_pwd(uid):
    """修改密码 (GET|POST&LOGIN)

    :uri: /users/<string:uid>/change-password
    :param old_pwd: 旧密码
    :param new_pwd: 新密码
    :returns: {}
    """
    user = request.authed_user
    params = request.values
    old_pwd = params.get('old_pwd', None)
    new_pwd = params.get('new_pwd', None)
    user = User.login(user.name, old_pwd)
    if not user:
        return error.AuthFailed('原密码不正确')

    invalid_error = User.invalid_password(new_pwd)
    if invalid_error:
        return invalid_error

    User.change_pwd(user, new_pwd)
    return {}


# TODO: being delete uid param
@app.route("/users/<string:uid>/modify-info", methods=('POST', 'GET'))
@util.jsonapi(login_required=True)
def modify_info(uid):
    """修改用户信息 (GET|POST&LOGIN)

    :uri: /users/<string:uid>/modify-info
    :param nickname: 昵称
    :param phone: 手机
    :param birthday: 生日
    :param email: 邮箱
    :param gender: 性别(1:男, 2:女)
    :param signature: 签名
    :param announcement: 公告
    :returns: {'user': object}
    """
    user = request.authed_user
    params = request.values
    nickname = params.get('nickname', None)

    signature = params.get('signature', None)
    if signature:
        if Spam.filter_words(signature, 'signature'):
            return error.InvalidContent

    announcement = params.get('announcement', None)
    if announcement:
        if Spam.filter_words(announcement, 'announcement'):
            return error.InvalidContent

    if nickname:
        invalid_error = User.invalid_nickname(nickname)
        if invalid_error:
            return invalid_error

    info = dict()
    for key in const.USER_ALLOWED_MODIFY:
        if params.get(key, None):
            info[key] = const.USER_ALLOWED_MODIFY[key](params[key])
    if 'gender' in info and info['gender'] not in [1, 2]:
        return error.InvalidArguments
    info['update_at'] = time.time()
    user = user.update_model({'$set': info})
    return {'user': user.format()}


# TODO: being delete opt in url
@app.route("/user/opt/follow-user", methods=('POST', 'GET'))
@util.jsonapi(login_required=True)
def follow_user():
    """关注用户 (GET|POST&LOGIN)

    :uri: /user/opt/follow-user
    :param target_user_id: 被关注用户id
    :returns: {}
    """
    user = request.authed_user
    params = request.values
    target_uid = params.get('target_user_id', None)
    target_user = User.get_one(target_uid)
    if not target_user:
        return error.UserNotExist

    if target_uid == str(user._id):
        return error.FollowFailed("不能关注自己哦")

    fs = FriendShip.get_by_ship(str(user._id), target_uid)
    if not fs:
        key = 'lock:follow:%s:%s' % (str(user._id), target_uid)
        with util.Lockit(Redis, key) as locked:
            if locked:
                return error.FollowFailed

            fs = FriendShip.init()
            fs.source = ObjectId(str(user._id))
            fs.target = ObjectId(target_uid)
            fs.create_model()
            # 关注主播任务检查
            if user:
                UserTask.check_user_tasks(str(user._id), FOLLOW_USER, 1)

    return {}


# TODO: being delete opt in url
@app.route("/user/opt/unfollow-user", methods=('POST', 'GET'))
@util.jsonapi(login_required=True)
def unfollow_user():
    """取消关注用户 (GET|POST&LOGIN)

    :uri: /user/opt/unfollow-user
    :param target_user_id: 被取消关注用户id
    :returns: {}
    """
    user = request.authed_user
    params = request.values
    target_uid = params.get('target_user_id', None)
    target_user = User.get_one(target_uid)
    if not target_user:
        return error.UserNotExist

    key = 'lock:unfollow:%s:%s' % (str(user._id), target_uid)
    with util.Lockit(Redis, key) as locked:
        if locked:
            return error.FollowFailed('取消关注失败')
        fs = FriendShip.get_by_ship(str(user._id), target_uid)
        fs.delete_model() if fs else None
    return {}


@app.route('/users/<string:uid>/followers', methods=['GET'])
@util.jsonapi()
def followers(uid):
    """获取用户粉丝 (GET)

    :uri: /users/<string:uid>/followers
    :param maxs: 最后时间, 0代表当前时间, 无此参数按page来分页
    :param page: 页码(数据可能有重复, 建议按照maxs分页)
    :param nbr: 每页数量
    :returns: {'users': list}
    """
    params = request.values
    maxs = params.get('maxs', None)
    maxs = time.time() if maxs is not None and int(float(maxs)) == 0 else maxs and float(maxs)
    page = int(params.get('page', 1))
    pagesize = int(params.get('nbr', 10))

    users = list()
    uids = list()
    while len(users) < pagesize:
        uids = FriendShip.follower_ids(uid, page, pagesize, maxs)
        users.extend([u.format() for u in User.get_list(uids)])

        # 如果按照maxs分页, 不足pagesize个记录则继续查询
        if maxs is not None:
            obj = FriendShip.get_by_ship(uids[-1], uid) if uids else None
            maxs = obj.create_at if obj else 1000
            if len(uids) < pagesize:
                break
        else:
            break

    return {'users': users, 'end_page': len(uids) != pagesize, 'maxs': maxs}


@app.route('/users/<string:uid>/followings', methods=['GET'])
@util.jsonapi()
def followings(uid):
    """获取用户的偶像 (GET)

    :uri: /users/<string:uid>/followings
    :param maxs: 最后时间, 0代表当前时间, 无此参数按page来分页
    :param page: 页码(数据可能有重复, 建议按照maxs分页)
    :param nbr: 每页数量
    :returns: {'users': list}
    """
    params = request.values
    maxs = params.get('maxs', None)
    maxs = time.time() if maxs is not None and int(float(maxs)) == 0 else maxs and float(maxs)
    page = int(params.get('page', 1))
    pagesize = int(params.get('nbr', 10))

    users = list()
    uids = list()
    while len(users) < pagesize:
        uids = FriendShip.following_ids(uid, page, pagesize, maxs)
        users.extend([u.format() for u in User.get_list(uids)])

        # 如果按照maxs分页, 不足pagesize个记录则继续查询
        if maxs is not None:
            obj = FriendShip.get_by_ship(uid, uids[-1]) if uids else None
            maxs = obj.create_at if obj else 1000
            if len(uids) < pagesize:
                break
        else:
            break

    return {'users': users, 'end_page': len(uids) != pagesize, 'maxs': maxs}


@app.route('/users/contacts', methods=['GET'])
@util.jsonapi(login_required=True)
def contacts():
    """获取用户的联系人 (GET)

    :uri: /users/contacts
    :returns: {'users': list}
    """
    user = request.authed_user

    uids = FriendShip.contact_ids(str(user._id))
    _users = [u.format(exclude_fields=['is_followed']) for u in User.get_list(uids)]
    # 根据nickname(中文转换为拼音)进行排序
    pinyin = Pinyin()
    users = []
    for u in _users:
        u['nickpy'] = pinyin.get_pinyin(u['nickname'], '')
        users.append(u)

    users = sorted(users, key=lambda x: x['nickpy'].lower())
    return {'users': users}


@app.route('/games/<string:gid>/popularusers', methods=['GET'])
@util.jsonapi()
def game_popular_users(gid):
    """获取游戏热门用户 (GET)

    :uri: /games/<string:gid>/popularusers
    :param page: 页码
    :param nbr: 每页数量
    :returns: {'users': list, 'end_page': bool}
    """
    params = request.values
    page = int(params.get('page', 1))
    pagesize = int(params.get('nbr', 10))
    uids = Game.popular_user_ids(gid, page, pagesize)
    users = [u.format() for u in User.get_list(uids)]
    return {'users': users, 'end_page': len(uids) != pagesize}


@app.route('/recommend/users', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def recommend_users():
    """获取推荐关注 (GET&LOGIN)

    :uri: /recommend/users
    :returns: {'users': list}
    """
    user = request.authed_user
    uids = []
    gids = UserSubGame.sub_game_ids(str(user._id))
    for gid in gids:
        uids.extend(Game.popular_user_ids(gid))
    if not uids:
        uids = User.user_recommend_attention()
    uids = list(set(uids))
    if str(user._id) in uids:
        uids.remove(str(user._id))
    if len(uids) > const.RECOMMEND_ATTENTION:
        uids = random.sample(uids, const.RECOMMEND_ATTENTION)
    users = [u.format() for u in User.get_list(uids)]
    return {'users': users}


@app.route('/users/share', methods=['POST'])
@util.jsonapi()
def share_video():
    """分享视频 (POST)

    :uri: /users/share
    :param platform: 分享平台(moments, qzone, qq, weixin, other)
    :param target_type:分享数据类型(video, game, live, url)
    :param target_value: 分享数据值
    :returns: {}
    """
    user = request.authed_user
    params = request.values
    platform = params.get('platform', 'other')
    target_type = params.get('target_type', 'video')
    target_value = params.get('target_value')

    if not platform:
        return error.InvalidArguments

    rv = UserShare.init()
    rv.user = str(user._id) if user else None
    rv.platform = platform
    rv.target_type = target_type
    rv.target_value = target_value
    rv.create_model()
    # 分享视频任务检查
    if user and target_type == 'video':
        UserTask.check_user_tasks(str(user._id), SHARE_VIDEO, 1)

    return {}
