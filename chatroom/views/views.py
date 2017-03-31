# coding: utf-8
from django.http import HttpResponse
from settings import STATIC_ROOT
from rest_framework import permissions
from rest_framework.request import Request

# Create your views here.
def sendmail(request):
    from django.core.mail import send_mail
    send_mail('Subject here', 'Here is the message.', 'pigroom <1990815733@qq.com>', ['hi_youjiajia@163.com'])
    return HttpResponse(STATIC_ROOT)


from rest_framework import viewsets
from chatroom.models.user import UserProfile
from chatroom.serializer.user import OwnerProfileSerializer


class UserViewSet(viewsets.ModelViewSet):
    """

    允许查看和编辑user 的 API endpoint
    """
    queryset = Request.user.profile
    serializer_class = OwnerProfileSerializer
    permission_classes = (permissions.IsAuthenticated,)
