# -*- coding: utf8 -*-
from bson.objectid import ObjectId
from flask import request
from wanx import app
from wanx.models.user import User
from wanx.models.video import Video
from wanx.models.game import Game, Category, CategoryGame
from wanx.models.comment import Comment, Reply
from wanx.base import util, error, const
from wanx.platforms import Migu


import random
import time


@app.route('/migu/home/', methods=['GET'])
@util.jsonapi(verify=False)
def migu_home():
    """获取首页信息 (GET)

    :uri: /migu/home/
    :returns: {'popular': list, 'whats_new': list,
              'hottest_of_today': list, 'recommend': list, 'tags': list}
    """
    ret = dict()
    ret['popular'] = []
    ret['whats_new'] = []
    ret['hottest_of_today'] = []
    ret['recommend'] = []

    tags = []
    cids = Category.all_category_ids()
    categories = Category.get_list(cids)
    for category in categories:
        gids = CategoryGame.category_game_ids(str(category._id))
        games = [g.format() for g in Game.get_list(gids)]
        tags.append(dict(games=games, tag_id=str(
            category._id), name=category.name))

    ret['tags'] = tags

    return ret


@app.route('/migu/users/<string:openid>/videos/', methods=['GET'])
@util.jsonapi(verify=False)
def migu_user_videos(openid):
    """获取用户创建的视频 (GET)

    :uri: /migu/users/<string:openid>/videos/
    :param game_id: 咪咕游戏id, 不传取用户所有游戏的视频
    :param maxs: 最后时间, 0代表当前时间, 无此参数按page来分页
    :param page: 页码(数据可能有重复, 建议按照maxs分页)
    :param nbr: 每页数量
    :returns: {'videos': list, 'end_page': bool, 'maxs': timestamp}
    """
    params = request.values
    maxs = params.get('maxs', None)
    maxs = time.time() if maxs is not None and int(
            float(maxs)) == 0 else maxs and float(maxs)
    page = int(params.get('page', 1))
    pagesize = int(params.get('nbr', 10))
    bid = params.get('game_id', None)

    game = Game.get_by_bid(bid)
    gid = str(game._id) if game else None
    user = User.get_platform_user('migu', openid)
    if not user:
        return error.UserNotExist
    uid = str(user._id)

    videos = list()
    vids = list()
    while len(videos) < pagesize:
        if gid:
            vids = Video.user_game_video_ids(uid, gid, page, pagesize, maxs)
        else:
            vids = Video.user_video_ids(uid, page, pagesize, maxs)

        for video in Video.get_list(vids):
            game = Game.get_one(str(video.game))
            # 过滤掉不是咪咕大厅游戏(游戏bid字段为空)的视频
            if game and game.bid:
                videos.append(video.format())

        # 如果按照maxs分页, 不足pagesize个记录则继续查询
        if maxs is not None:
            obj = Video.get_one(vids[-1], check_online=False) if vids else None
            maxs = obj.create_at if obj else 1000
            if len(vids) < pagesize:
                break
        else:
            break

    return {'videos': videos, 'end_page': len(vids) != pagesize, 'maxs': maxs}


@app.route('/migu/videos/<string:vid>/comments/submit', methods=('GET', 'POST'))
@util.jsonapi(verify=False)
def migu_create_comment(vid):
    """咪咕平台创建评论 (GET|POST)

    :uri: /migu/videos/<string:vid>/comments/submit
    :param user_id: 咪咕用户id
    :param content: 评论内容
    :returns: {}
    """
    params = request.values
    openid = params.get('user_id', '')
    content = params.get('content', '')
    if len(openid) < 1 or len(content) < 1:
        return error.InvalidArguments

    video = Video.get_one(vid)
    if not video:
        return error.VideoNotExist
    user = User.get_platform_user('migu', openid)
    if not user:
        info = dict(name='$mg$%s%s' %
                (openid[-4:], random.randint(1000, 9999)))
        user = User.create_platform_user('migu', openid, data=info)
    comment = Comment.init()
    comment.author = ObjectId(str(user._id))
    comment.content = content
    comment.video = ObjectId(vid)
    comment.create_model()
    return {}


@app.route('/migu/videos/<string:vid>/comments/', methods=['GET'])
@util.jsonapi()
def migu_video_comments(vid):
    """获取视频评论 (GET)

    :uri: /migu/videos/<string:vid>/comments/
    :param maxs: 最后时间, 0代表当前时间, 无此参数按page来分页
    :param page: 页码(数据可能有重复, 建议按照maxs分页)
    :param nbr: 每页数量
    :returns: {'comments': list, 'end_page': bool, 'maxs': timestamp}
    """
    params = request.values
    maxs = params.get('maxs', None)
    maxs = time.time() if maxs is not None and int(float(maxs)) == 0 else maxs and float(maxs)
    page = int(params.get('page', 1))
    pagesize = int(params.get('nbr', 10))

    comments = list()
    cids = list()
    next_maxs = None
    while len(comments) < pagesize:
        cids = Comment.video_comment_ids(vid, page, pagesize, maxs)
        comments.extend([c.format() for c in Comment.get_list(cids)])

        # 如果按照maxs分页, 不足pagesize个记录则继续查询
        if maxs is not None:
            obj = Comment.get_one(cids[-1], check_online=False) if cids else None
            next_maxs = obj.create_at if obj else 1000
            if len(cids) < pagesize:
                break
        else:
            break

    end_page = len(cids) < pagesize

    # 评论增加3个回复
    for comment in comments:
        rids = Reply.comment_reply_ids(comment['comment_id'], 1, 4, 0)
        comment['replies'] = [r.format() for r in Reply.get_list(rids)]

    return {'comments': comments, 'end_page': end_page, 'maxs': next_maxs}


@app.route('/migu/games/<string:bid>/popular/', methods=['GET'])
@util.jsonapi(verify=False)
def migu_game_popular_videos(bid):
    """获取游戏热门视频 (GET)

    :uri: /migu/games/<string:bid>/popular/
    :param page: 页码
    :param nbr: 每页数量
    :returns: {'videos': list, 'end_page': bool}
    """
    params = request.values
    page = int(params.get('page', 1))
    pagesize = int(params.get('nbr', 10))
    game = Game.get_by_bid(bid)
    if not game:
        return error.GameNotExist
    vids = Video.game_hotvideo_ids(str(game._id), page, pagesize)
    videos = [v.format() for v in Video.get_list(vids)]
    ret = {'videos': videos, 'end_page': len(vids) != pagesize}
    return ret


@app.route('/migu/tags/home/', methods=['GET'])
@util.jsonapi(verify=False)
def migu_all_tags():
    """获取所有标签 (GET)

    :uri: /migu/tags/home/
    :returns: {'tags': list}
    """
    cids = Category.all_category_ids()
    categories = Category.get_list(cids)
    tags = [{str(c._id): c.name} for c in categories]
    return {'tags': tags}


@app.route('/migu/videos/elite/', methods=['GET'])
@util.jsonapi(verify=False)
def migu_elite_video():
    """获取精选视频 (GET)

    :uri: /migu/videos/elite/
    :param maxs: 最后时间, 0代表当前时间, 无此参数按page来分页
    :param page: 页码(数据可能有重复, 建议按照maxs分页)
    :param nbr: 每页数量
    :returns: {'videos': list, 'end_page': bool, 'maxs': timestamp}
    """
    params = request.values
    maxs = params.get('maxs', None)
    maxs = time.time() if maxs is not None and int(
            float(maxs)) == 0 else maxs and float(maxs)
    page = int(params.get('page', 1))
    pagesize = int(params.get('nbr', 10))

    videos = list()
    vids = list()
    while len(videos) < pagesize:
        vids = Video.elite_video_ids(page, pagesize, maxs)
        for video in Video.get_list(vids):
            game = Game.get_one(str(video.game))
            # 过滤掉不是咪咕大厅游戏(游戏bid字段为空)的视频
            if game and game.bid:
                videos.append(video.format())

        # 如果按照maxs分页, 不足pagesize个记录则继续查询
        if maxs is not None:
            obj = Video.get_one(vids[-1], check_online=False) if vids else None
            maxs = obj.release_time if obj else 1000
            if len(vids) < pagesize:
                break
        else:
            break

    return {'videos': videos, 'end_page': len(vids) != pagesize, 'maxs': maxs}


@app.route('/migu/change_password', methods=('POST', 'GET'))
@util.jsonapi()
def migu_change_pwd():
    """更改密码（GET|POST）

    :uri: /migu/change_password
    :param phone: 手机号
    :param old_pwd: 旧密码
    :param new_pwd: 新密码
    :returns: {}
    """
    user = request.authed_user
    params = request.values
    old_pwd = params.get('old_pwd', None)
    new_pwd = params.get('new_pwd', None)
    phone = params.get('phone', None) or (user and user.phone)

    if not old_pwd or not new_pwd or not phone:
        return error.InvalidArguments

    invalid_error = User.invalid_password(new_pwd)
    if invalid_error:
        return invalid_error

    openid = Migu.get_identityid(phone, old_pwd, const.CENTER_ACCOUNT_PHONE)
    if isinstance(openid, error.ApiError):
        return openid

    ret = Migu.center_update_pwd(openid, old_pwd, new_pwd)
    if isinstance(ret, error.ApiError):
        return ret

    return {}


@app.route("/migu/register_phone", methods=("POST", "GET",))
@util.jsonapi()
def migu_register():
    """用户注册（GET|POST）

    :uri: /migu/register_phone
    :param phone: 手机号
    :param password: 密码
    :param code: 验证码
    :param sessionid: 短信sessionid
    :returns: {'user': object, 'ut': string}
    """
    params = request.values.to_dict()
    phone = params.get('phone', None)
    code = params.get('code', None)
    sessionid = params.get('sessionid', None)
    password = params.get('password', None)
    if not phone or not code or not password or not sessionid:
        return error.InvalidArguments

    invalid_error = User.invalid_password(password)
    if invalid_error:
        return invalid_error

    # 用户中心注册
    ret = Migu.center_register(phone, password, const.CENTER_ACCOUNT_PHONE, code, sessionid)
    if isinstance(ret, error.ApiError):
        return ret

    # 进行用户绑定
    migu_uid = Migu.get_identityid(phone, password, const.CENTER_ACCOUNT_PHONE)
    if isinstance(migu_uid, error.ApiError):
        return migu_uid

    user = User.get_platform_user('migu', migu_uid)
    if not user:
        user = User.get_by_phone(phone)
        if user:
            info = dict(
                    partner_migu={'id': migu_uid},
                    nickname=u'咪咕用户%s%s' % (migu_uid[-4:], random.randint(1000, 9999)),
                    gender=random.randint(1, 2),
                    name='$mg$%s%s' % (migu_uid[-4:], random.randint(1000, 9999))
                    )
            user = user.update_model({'$set': info})
        else:
            info = dict(
                    phone=phone,
                    nickname=u'咪咕用户%s%s' % (migu_uid[-4:], random.randint(1000, 9999)),
                    gender=random.randint(1, 2),
                    name='$mg$%s%s' % (migu_uid[-4:], random.randint(1000, 9999))
                    )
            user = User.create_platform_user('migu', migu_uid, data=info)
    else:
        # 如果用户没有绑定手机并且手机号没有被绑定, 则自动进行手机号绑定
        if not user.phone and not User.get_by_phone(phone):
            info = dict(phone=phone)
            user.update_model({'$set': info})

    ut = User.gen_token(str(user._id))
    return {'user': user.format(), 'ut': ut}


@app.route("/migu/reset_password", methods=("POST", "GET",))
@util.jsonapi()
def migu_reset_password():
    """重置密码 (GET|POST)

    :uri: /migu/reset_password
    :param phone: 手机号
    :param password: 密码
    :param code: 短信验证码
    :param sessionid: 短信sessionid
    :returns: {}
    """
    params = request.values.to_dict()
    phone = params.get('phone', None)
    code = params.get('code', None)
    sessionid = params.get('sessionid', None)
    password = params.get("password", None)
    if not phone or not code or not password or not sessionid:
        return error.InvalidArguments

    invalid_error = User.invalid_password(password)
    if invalid_error:
        return invalid_error

    ret = Migu.center_reset_pwd(phone, password, const.CENTER_ACCOUNT_PHONE, code, sessionid)
    if isinstance(ret, error.ApiError):
        return ret

    return {}


@app.route("/migu/verify_phone", methods=("POST", "GET",))
@util.jsonapi()
def migu_verify_phone():
    """手机号码验证 (GET|POST)

    :uri: /migu/verify_phone
    :param phone: 手机号
    :returns: {}
    """
    params = request.values.to_dict()
    phone = params.get('phone', None)

    if not phone:
        return error.InvalidArguments
    ret = Migu.center_check_account(phone, const.CENTER_ACCOUNT_PHONE)
    if isinstance(ret, error.ApiError):
        return ret
    elif not ret:
        return error.UserExists("手机号已被注册")

    return {}


@app.route("/migu/sms_code", methods=("POST", "GET"))
@util.jsonapi()
def send_migu_code():
    """发送短信验证码 (GET|POST)

    :uri: /migu/sms_code
    :param phone: 手机号
    :param action: (注册:reg  重置:reset  升级:up)
    :returns: {'sessionid': string}
    """
    params = request.values
    phone = params.get('phone', None)
    action = params.get('action', None)
    if not phone:
        return error.InvalidArguments
    # 如果是注册验证码,提前判断手机号是否已存在
    ret = Migu.center_check_account(phone, const.CENTER_ACCOUNT_PHONE)
    if isinstance(ret, error.ApiError):
        return ret
    if action == 'reg' and not ret:
        return error.UserExists

    ret = Migu.center_sms_code(phone, action)
    if isinstance(ret, error.ApiError):
        return ret

    return {'sessionid': ret}


@app.route("/migu/upgrade", methods=("POST", "GET"))
@util.jsonapi(login_required=True)
def service_up():
    """升级咪咕通行证 (GET|POST&LOGIN)

    :uri: /migu/upgrade
    :param phone: 手机号
    :param password: 升级密码
    :param code: 短信验证码
    :param sessionid: 短信sessionid
    :returns: {}
    """
    params = request.values
    phone = params.get('phone', None)
    password = params.get('password', None)
    code = params.get('code', None)
    sessionid = params.get('sessionid', None)
    if not phone or not password or not code or not sessionid:
        return error.InvalidArguments

    ret = Migu.center_service_up(phone, password, code, sessionid)
    if isinstance(ret, error.ApiError):
        return ret

    return {}


@app.route('/migu/hf-userid', methods=('GET', 'POST'))
@util.jsonapi(login_required=True)
def migu_hf_userid():
    user = request.authed_user
    hf_userid = Migu.get_user_info_by_account_name(str(user.phone), keyword='hfUserID')
    if isinstance(hf_userid, error.ApiError):
        return hf_userid

    return {'hf_userid': hf_userid}


