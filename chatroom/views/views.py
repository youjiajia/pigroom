# coding: utf-8
from django.http import HttpResponse
from rest_framework.response import Response

from settings import STATIC_ROOT
from chatroom.permissions import IsOwnerOrCreateOnly


# Create your views here.
def sendmail(request):
    from django.core.mail import send_mail
    send_mail('Subject here', 'Here is the message.', 'pigroom <1990815733@qq.com>', ['hi_youjiajia@163.com'])
    return HttpResponse(STATIC_ROOT)


from rest_framework import generics, mixins
from chatroom.models.user import UserProfile
from chatroom.serializer.user import OwnerProfileSerializer, OwnerChangeProfileSerializer


class UserViewSet(mixins.CreateModelMixin,
                  mixins.UpdateModelMixin, generics.GenericAPIView):
    """

    允许查看和编辑user 的 API endpoint
    """
    queryset = UserProfile.objects.all()
    serializer_class = OwnerChangeProfileSerializer
    permission_classes = (IsOwnerOrCreateOnly,)

    def get_serializer_class(self, *args, **kwargs):
        if self.request.method in ('GET',):
            return OwnerProfileSerializer
        return self.serializer_class
    #
    # def get(self, request, *args, **kwargs):
    #     print type(request.user)
    #     userPro = request.user.profile
    #     serializer = self.get_serializer(userPro)
    #     return Response(serializer.data)
