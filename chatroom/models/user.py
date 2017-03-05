from django.db import models
from django.contrib.auth.models import User
from rest_framework import serializers


class UserProfile(models.Model):
    user = models.OneToOneField(User)
    friends = models.ManyToManyField(User)
    nickname = models.CharField(max_length=200, default='', blank=True)
    phone = models.CharField(max_length=200, default='', blank=True)
    cover = models.CharField(max_length=200, default='', blank=True)
    friendcount = models.IntegerField(default=0, blank=True)
    gender = models.IntegerField(default=0, blank=True)
    update_at = models.DateTimeField()
    create_at = models.DateTimeField()


class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ('url', 'username', 'email', 'groups')
