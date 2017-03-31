# -*- coding: utf8 -*-
from django.db import models
from django.contrib.auth.models import User
from django_extensions.db.models import TimeStampedModel

from chatroom.base import const


class UserProfile(TimeStampedModel):
    user = models.OneToOneField(User, unique=True, db_index=True, related_name='profile')
    friends = models.ManyToManyField(User, through='Usership')
    nickname = models.CharField(max_length=200, default='', blank=True)
    phone = models.CharField(max_length=200, default='', blank=True)
    cover = models.CharField(max_length=200, default='', blank=True)
    friendcount = models.IntegerField(default=0, blank=True)
    gender = models.IntegerField(default=0, blank=True)
    status = models.IntegerField(default=0, blank=True)

    class Meta:
        db_table = "userprofile"
        app_label = "chatroom"
        ordering = ['-created']

    def __unicode__(self):
        return self.nickname


class Usership(TimeStampedModel):
    UserShipStatus = (
        (const.WAIT, '等待对方回应'),
        (const.AGREE, '成功'),
        (const.REFUSE, '拒绝'),
        (const.BLACK, '拉黑'),
        (const.DELETE, '删除好友')
    )
    Owner = models.ForeignKey(UserProfile, related_name='userOwner')
    Feedback = models.ForeignKey(User, related_name='userfeedbacks')
    note = models.CharField(max_length=200, blank=True, null=True)
    status = models.IntegerField(choices=UserShipStatus)

    class Meta:
        db_table = "usership"
        app_label = "chatroom"
        ordering = ['-created']

    def __unicode__(self):
        return self.note
