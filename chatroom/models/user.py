# -*- coding: utf8 -*-
from django.db import models
from django.contrib.auth.models import User as OldUser
from playhouse.shortcuts import model_to_dict
from chatroom.base.util import cached_object
from chatroom.base import const
from chatroom.models.base import BaseModel, CacheBase


class User(OldUser, CacheBase):
    pass


class UserProfile(BaseModel):
    UserStatus = (
        (const.WAITVERIFY, '待认证邮箱'),
        (const.REGISTERSUCCESS, '注册成功'),
        (const.BEBENED, '被封号'),
        (const.OVERDUE, '账号已经过期')
    )
    ENABLE_LOCAL_CACHE = True
    user = models.OneToOneField(OldUser, unique=True, db_index=True, related_name='profile')
    friends = models.ManyToManyField(OldUser, through='Usership')
    nickname = models.CharField(max_length=200, default='', blank=True)
    phone = models.CharField(max_length=200, default='', blank=True)
    cover = models.CharField(max_length=200, default='', blank=True)
    friendcount = models.IntegerField(default=0, blank=True)
    gender = models.IntegerField(default=0, blank=True)
    status = models.IntegerField(choices=UserStatus, default=0, blank=True)

    class Meta:
        db_table = "userprofile"
        app_label = "chatroom"
        ordering = ['-created']

    def __unicode__(self):
        return self.nickname

    @classmethod
    @cached_object(lambda cls, oid: cls.OBJECT_KEY % ({
        'name': cls.__name__.lower(), 'oid': str(oid)}))
    def _load_object(cls, oid):
        obj = cls.objects.get(user__id=oid)
        return model_to_dict(obj)


class Usership(BaseModel):
    UserShipStatus = (
        (const.WAIT, '等待对方回应'),
        (const.AGREE, '成功'),
        (const.REFUSE, '拒绝'),
        (const.BLACK, '拉黑'),
        (const.DELETE, '删除好友')
    )
    ENABLE_LOCAL_CACHE = True
    Owner = models.ForeignKey(UserProfile, related_name='userOwner')
    Feedback = models.ForeignKey(OldUser, related_name='userfeedbacks')
    note = models.CharField(max_length=200, blank=True, null=True)
    status = models.IntegerField(choices=UserShipStatus)

    class Meta:
        db_table = "usership"
        app_label = "chatroom"
        ordering = ['-created']

    def __unicode__(self):
        return self.note
