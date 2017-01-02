# -*- coding: utf8 -*-
"""
**点赞&评论消息实现:**

1. 服务端只保留增量的消息，也就是已经发送给客户端的消息服务端不再保留。
#. 客户端在获取/messages/home接口时，服务端会把用户的增量点赞&评论消息发送给客户端。
#. 客户端处理完之后，需要调用/messages/delete接口通知服务端ts时间之前的消息可以删除了。
#. 用户查看点赞&评论消息详情的时候客户端需要记录用户最后的阅读时间。

**系统消息实现:**

1. 服务端将会保留所有的历史系统消息。
#. 客户端在获取/messages/home接口时, 需要传送用户最后阅读的系统消息时间，
   服务端将会把这个时间之后的系统消息发送给客户端。
#. 用户查看系统消息详情的时候客户端需要记录用户最后的阅读时间。

**私信消息实现:**

1. 服务端只保留增量的消息，也就是已经发送给客户端的消息服务端不再保留。
#. 由于私信用户可能较多，客户端在获取/messages/home接口时, 服务端只会返回有新私信的用户的信息。
   这些信息只包括了新消息的条目、最后一条消息的内容。
#. 客户端通过调用/letters/detail接口来获取某个用户新私信的具体内容，户端需要记录用户最后的阅读时间
#. 客户端处理完之后，需要调用/letters/delete接口通知服务端ts时间之前的消息可以删除了。
"""
from flask import request
from wanx import app
from wanx.base import util, error
from wanx.models.msg import Message, SysMessage, Letter, Suggestion
from wanx.models.user import User

import time

from wanx.platforms import Migu


@app.route('/messages/home', methods=['GET', 'POST'])
@util.jsonapi()
def user_msg_home():
    """获取消息首页信息(GET|POST)

    :uri: /messages/home
    :param lrt: 系统消息最后阅读时间
    :returns: {'msgs': list, 'sys_msgs': list, 'letters': list}
    """
    user = request.authed_user
    params = request.values
    os = params.get('os', None)
    channels = params.get('channels', None)
    version_code = int(params.get('version_code', 0))
    ts = params.get('lrt', None)

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

    # 默认取7天前的系统个人消息
    cts = time.time()
    if ts:
        ts = ts_user = float(ts)
    else:
        ts_user = (cts - 7 * 24 * 3600)

    sys_msgs = []
    # 过滤系统消息（平台、渠道、版本、用户组、有效期）
    for msg in SysMessage.sys_new_messages(ts, cts):
        if msg.os and msg.os not in ['all', os]:
            continue

        if (msg.version_code_mix and msg.version_code_mix > version_code) or\
                (msg.version_code_max and msg.version_code_max < version_code):
            continue

        if channels and msg.channels and channels not in msg.channels:
            continue

        if msg.login == 'login' and (not uid or not msg.user_in_group(str(msg.group), uid)):
            continue

        if msg.province and not province:
            continue

        if province and province not in msg.province:
            continue

        sys_msgs.append(msg.format())

    msgs = []
    letters = []
    if user:
        uid = str(user._id)

        # 用户系统消息推送
        sys_user_msg = [msg.format() for msg in SysMessage.sys_user_messages(ts_user, uid)]
        sys_msgs.extend(sys_user_msg)

        msgs = [msg.format() for msg in Message.user_new_messages(uid)]
        letters = list()
        _letters = Letter.new_letter_count(uid)
        for _letter in _letters:
            last_letter = Letter.get_one(_letter['last_id'])
            temp = dict(
                last_letter=last_letter.format(),
                count=_letter['count']
            )
            letters.append(temp)
    return {'msgs': msgs, 'sys_msgs': sys_msgs, 'letters': letters}


@app.route('/messages/delete', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def delete_user_msgs():
    """删除点赞&评论消息(GET|POST&LOGIN)

    :uri: /messages/delete
    :param lrt: 点赞&评论消息最后阅读时间
    :returns: {'delete_count': int}
    """
    user = request.authed_user
    ts = float(request.values['lrt'])
    count = Message.delete_user_messages(str(user._id), ts)
    return {'delete_count': count}


@app.route('/letters/detail', methods=['GET'])
@util.jsonapi(login_required=True)
def user_letter_detail():
    """获取私信详情(GET&LOGIN)

    :uri: /letters/detail
    :param sender: 联系人ID
    :returns: {'letters': list}
    """
    user = request.authed_user
    sender = request.values.get('sender', None)
    if not sender:
        return error.InvalidArguments
    letters = [l.format() for l in Letter.user_new_letters(str(user._id), sender)]
    return {'letters': letters}


@app.route('/letters/delete', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def delete_user_letters():
    """删除用户私信(GET|POST&LOGIN)

    :uri: /letters/delete
    :param sender: 联系人ID
    :param lrt: 私信最后阅读时间
    :returns: {'delete_count': int}
    """
    user = request.authed_user
    sender = request.values.get('sender', None)
    if not sender:
        return error.InvalidArguments
    ts = float(request.values['lrt'])
    count = Letter.delete_user_letters(str(user._id), sender, ts)
    return {'delete_count': count}


@app.route('/letters/send', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def send_user_letter():
    """发送私信(GET|POST&LOGIN)

    :uri: /letters/send
    :param receiver: 接收者ID
    :param content: 发送内容
    :returns: {'letter': object}
    """
    user = request.authed_user
    to_user = request.values.get('receiver', None)
    content = request.values.get('content', None)
    if not to_user or not content:
        return error.InvalidArguments
    owner = User.get_one(to_user)
    if not owner:
        return error.UserNotExist
    letter = Letter.init()
    letter.owner = owner._id
    letter.sender = user._id
    letter.content = content
    _id = letter.create_model()
    letter = Letter.get_one(_id)
    return {'letter': letter.format()}


@app.route('/suggestion/commit', methods=['GET', 'POST'])
@util.jsonapi()
def commit_suggestion():
    """提交意见反馈(GET|POST)

    :uri: /suggestion/commit
    :param contact: 联系方式
    :param content: 意见内容(不能为空)
    :returns: {'ret': bool}
    """
    user = request.authed_user
    contact = request.values.get('contact', None)
    content = request.values.get('content', None)
    if not content:
        return error.InvalidArguments('意见内容不能为空')

    sugg = Suggestion.init()
    sugg.contact = contact
    sugg.content = content
    if user:
        sugg.user = user._id
    sugg.create_model()
    return {'ret': True}
