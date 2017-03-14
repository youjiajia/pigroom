# -*- coding:utf8 -*-
from rest_framework import serializers

from chatroom.models.user import UserProfile, User, Usership


class OwnerProfileSerializer(serializers.HyperlinkedModelSerializer):
    friends = UserProfileSerializer(many=True, user='self.owner')

    def __init__(self, user, **kwargs):
        self.owner = user
        super(OwnerProfileSerializer, self).__init__(**kwargs)

    class Meta:
        model = UserProfile
        fields = ('nickname', 'friendcount', 'phone', 'gender')


class UserProfileSerializer(serializers.HyperlinkedModelSerializer):
    notename = serializers.SerializerMethodField()

    def get_notename(self, user):
        return ""

    def __init__(self, user, **kwargs):
        self.owner = user
        super(UserProfileSerializer, self).__init__(**kwargs)

    class Meta:
        model = UserProfile
        fields = ('id', 'nickname', 'gender', 'cover', 'notename')
