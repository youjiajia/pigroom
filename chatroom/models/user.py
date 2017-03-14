from django.db import models
from django.contrib.auth.models import User
from rest_framework import serializers
from django_extensions.db.models import TimeStampedModel


class UserProfile(TimeStampedModel):
    user = models.OneToOneField(User, unique=True, db_index=True, related_name='profile')
    friends = models.ManyToManyField(User, through='Usership')
    nickname = models.CharField(max_length=200, default='', blank=True)
    phone = models.CharField(max_length=200, default='', blank=True)
    cover = models.CharField(max_length=200, default='', blank=True)
    friendcount = models.IntegerField(default=0, blank=True)
    gender = models.IntegerField(default=0, blank=True)

    class Meta:
        db_table = "userprofile"
        app_label = "chatroom"
        ordering = ['-created']

    def __unicode__(self):
        return self.nickname


class Usership(TimeStampedModel):
    Applyer = models.ForeignKey(UserProfile)
    Feedback = models.ForeignKey(User)
    note = models.CharField(max_length=200, blank=True, null=True)


class UserProfileSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = UserProfile
        fields = ('nickname', 'friendcount', 'phone', 'gender')
