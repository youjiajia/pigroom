# -*- coding:utf8 -*-
from rest_framework import serializers

from chatroom.models.user import UserProfile, User


class UserProfileSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = UserProfile
        fields = ('nickname', 'friendcount', 'phone', 'gender')
