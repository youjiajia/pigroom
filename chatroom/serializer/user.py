# -*- coding:utf8 -*-
from rest_framework import serializers

from chatroom.models.user import UserProfile, User, Usership


class OwnerProfileSerializer(serializers.HyperlinkedModelSerializer):
    friends = UserFriendSerializer(many=True)

    class Meta:
        model = UserProfile
        fields = ('nickname', 'friends', 'friendcount', 'phone', 'gender')


class UserFriendSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = Usership
        fields = ('Feedback__id', 'note', 'Feedback__gender', 'Feedback__cover', 'Feedback__nickname')
