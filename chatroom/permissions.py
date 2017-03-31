# -*- coding:utf8 -*-
from rest_framework import permissions


class IsOwnerOrCreateOnly(permissions.BasePermission):
    """
    自定义权限，只有创建者才能编辑查看
    """

    def has_object_permission(self, request, view, obj):
        if request.method in ('CREATE',):
            return True
        return False
