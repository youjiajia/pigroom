# -*- coding:utf8 -*-
from rest_framework import serializers

from chatroom.models.user import UserProfile, User, Usership


class OwnerProfileSerializer(serializers.HyperlinkedModelSerializer):
    friends = UserFriendSerializer(many=True)

    class Meta:
        model = UserProfile
        fields = ('nickname', 'friends', 'friendcount', 'phone', 'gender', 'status')


class UserFriendSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.ReadOnlyField(source='Feedback.id')
    gender = serializers.ReadOnlyField(source='Feedback.gender')
    cover = serializers.ReadOnlyField(source='Feedback.cover')
    nickname = serializers.ReadOnlyField(source='Feedback.nickname')

    class Meta:
        model = Usership
        fields = ('id', 'note', 'gender', 'cover', 'nickname')


class OwnerChangeProfileSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = UserProfile
        fields = ('nickname', 'phone', 'cover', 'gender')
