# coding: utf-8
from django.http import HttpResponse
from settings import STATIC_ROOT

# Create your views here.
def sendmail(request):
    from django.core.mail import send_mail
    send_mail('Subject here', 'Here is the message.', 'pigroom <1990815733@qq.com>', ['hi_youjiajia@163.com'])
    return HttpResponse(STATIC_ROOT)


from rest_framework import viewsets
from chatroom.models.user import UserProfileSerializer, UserProfile


class UserViewSet(viewsets.ModelViewSet):
    """
    允许查看和编辑user 的 API endpoint
    """
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
