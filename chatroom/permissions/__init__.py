# -*- coding:utf8 -*-
from rest_framework import permissions
from rest_framework.compat import is_authenticated


class IsOwnerOrCreateOnly(permissions.BasePermission):
    """
    自定义权限，只有创建者才能编辑查看
    """

    def has_object_permission(self, request, view, obj):
        if request.method in ('CREATE',):
            return True
        if request.user and is_authenticated(request.user):
            return True
        return False
