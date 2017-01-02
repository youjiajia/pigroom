# -*- coding: utf8 -*-
from flask import request
from wanx import app
from wanx.base import util, error
from wanx.base.xredis import MRedis
from wanx.models.user import User
from wanx.models.msg import SysMessage

import json
import time
import gevent

from wanx.platforms import Migu


@app.route('/async/test', methods=['GET'])
@util.jsonapi()
def async_test():
    return 'hello world'


@app.route('/async/msg', methods=['GET', 'POST'])
@util.jsonapi()
def async_msg():
    """服务器给客户端发消息接口(GET|POST)

    :uri: /async/msg
    :returns: {'has_new_msg': bool, 'has_new_follow': bool, 'has_new_task': bool}
    """
    user = request.authed_user
    params = request.values
    os = params.get('os', None)
    channels = params.get('channels', None)
    version_code = int(params.get('version_code', 0))

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

    retry_seconds = 60
    retry_times = 0
    msgs = []
    while len(msgs) <= 0 and retry_times < 10:
        ts = time.time()
        if user:
            pubsub = MRedis.pubsub()
            with gevent.Timeout(retry_seconds, False):
                user_channel = User.USER_ASYNC_MSG % ({'uid': uid})
                pubsub.subscribe(user_channel)
                for item in pubsub.listen():
                    if item['type'] == 'message':
                        msgs.append(item['data'])
                        break
                pubsub.unsubscribe(user_channel)

            pubsub.close()
            msgs = [json.loads(m) for m in msgs]

            # 获取发给用户的系统消息
            for sys_msg in SysMessage.sys_user_messages(ts, uid):
                _msg = dict(obj_type='SysMessage', obj_id=str(sys_msg._id), count=1)
                msgs.append(_msg)
        else:
            time.sleep(retry_seconds)

        # 获取并过滤系统消息（平台、渠道、版本、用户组、有效期）
        for msg in SysMessage.sys_new_messages(ts, time.time()):
            if msg.os and msg.os not in ['all', os]:
                continue

            if (msg.version_code_mix and msg.version_code_mix > version_code) or \
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

            _msg = dict(obj_type='SysMessage', obj_id=str(msg._id), count=1)
            msgs.append(_msg)
            break

        retry_times += 1

    has_new_msg = False
    has_new_follow = False
    has_new_task = False
    for msg in msgs:
        if msg['obj_type'] == 'FriendShip':
            has_new_follow = True
        elif msg['obj_type'] == 'Message':
            has_new_msg = True
        elif msg['obj_type'] == 'Letter':
            has_new_msg = True
        elif msg['obj_type'] == 'SysMessage':
            has_new_msg = True
        elif msg['obj_type'] == 'Task':
            has_new_task = True

    return {'has_new_msg': has_new_msg,
            'has_new_follow': has_new_follow,
            'has_new_task': has_new_task}
