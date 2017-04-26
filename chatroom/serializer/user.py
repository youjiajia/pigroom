# -*- coding:utf8 -*-
from rest_framework import serializers

from chatroom.models.user import UserProfile, User, Usership
from django.contrib.auth.hashers import make_password
from chatroom.serializer import HyperlinkedModelSerializer, ModelSerializer


class UserFriendSerializer(HyperlinkedModelSerializer):
    id = serializers.ReadOnlyField(source='Feedback.id')
    gender = serializers.ReadOnlyField(source='Feedback.gender')
    cover = serializers.ReadOnlyField(source='Feedback.cover')
    nickname = serializers.ReadOnlyField(source='Feedback.nickname')

    class Meta:
        model = Usership
        fields = ('id', 'note', 'gender', 'cover', 'nickname')


class OwnerProfileSerializer(HyperlinkedModelSerializer):
    friends = UserFriendSerializer(many=True)

    class Meta:
        model = UserProfile
        fields = ('nickname', 'friends', 'friendcount', 'phone', 'gender', 'status')


class OwnerChangeProfileSerializer(ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ('user', 'nickname', 'phone', 'cover', 'gender')


class UserSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ('username', 'password', 'email')

    # def create(self, validated_data):
    #     serializers.raise_errors_on_nested_writes('create', self, validated_data)
    #     ModelClass = self.Meta.model
    #     object = ModelClass.objects.create(
    #         username=validated_data['username'],
    #         password=make_password(validated_data['password']),
    #         email=validated_data.get('email', "")
    #     )
    #     return object
