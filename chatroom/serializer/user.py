# -*- coding:utf8 -*-
from rest_framework import serializers

from chatroom.models.user import UserProfile, User, Usership


class UserFriendSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.ReadOnlyField(source='Feedback.id')
    gender = serializers.ReadOnlyField(source='Feedback.gender')
    cover = serializers.ReadOnlyField(source='Feedback.cover')
    nickname = serializers.ReadOnlyField(source='Feedback.nickname')

    class Meta:
        model = Usership
        fields = ('id', 'note', 'gender', 'cover', 'nickname')


class OwnerProfileSerializer(serializers.HyperlinkedModelSerializer):
    friends = UserFriendSerializer(many=True)

    class Meta:
        model = UserProfile
        fields = ('nickname', 'friends', 'friendcount', 'phone', 'gender', 'status')


class OwnerChangeProfileSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = UserProfile
        fields = ('user', 'nickname', 'phone', 'cover', 'gender')


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('username', 'password', 'email')

    def create(self, validated_data):
        serializers.raise_errors_on_nested_writes('create', self, validated_data)
        ModelClass = self.Meta.model
        object = ModelClass()
        object.username = validated_data['username']
        object.set_password(validated_data['password'])
        object.email = validated_data['email']
        object.save()
        return object.id
