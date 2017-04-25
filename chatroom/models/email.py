# -*- coding: utf8 -*-
from chatroom.base.xredis import Redis
from django.contrib.auth.models import User
from chatroom.base import const, util
from chatroom.models.user import UserProfile

import base64, os


class VerifyEmail(object):
    EMAILTOKEN = "email:token:{token}"
    EXTIME = 12 * 3600

    @classmethod
    def get_email(cls, uid):
        token = base64.b64encode(os.urandom(15), "-.")
        key = cls.EMAILTOKEN.format(token=token)
        Redis.set(key, uid, ex=cls.EXTIME)
        return token

    @classmethod
    def checkouttoken(cls, email, token):
        key = cls.EMAILTOKEN.format(token=token)
        uid = Redis.get(key)
        if not uid:
            return False
        up = UserProfile.objects.get(user__id=uid)
        if not up or util.get_md5(up.user.email) != email:
            return False
        up.status = const.REGISTERSUCCESS
        up.save()
        return True


