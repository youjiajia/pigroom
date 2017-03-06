from django.db import models
from django.contrib.auth.models import User
from rest_framework import serializers
from django


class UserProfile(models.Model):
    user = models.OneToOneField(User)
    friends = models.ManyToManyField(User)
    nickname = models.CharField(max_length=200, default='', blank=True)
    phone = models.CharField(max_length=200, default='', blank=True)
    cover = models.CharField(max_length=200, default='', blank=True)
    friendcount = models.IntegerField(default=0, blank=True)
    gender = models.IntegerField(default=0, blank=True)

    class Meta:
        db_table = "auth_userprofile"
        app_label = "chatroom"created

    def __unicode__(self):
        return self.nickname


class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = UserProfile
        fields = ('nickname', 'friends', 'phone', 'user')
