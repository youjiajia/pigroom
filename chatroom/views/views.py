# coding: utf-8
from django.http import HttpResponse
from rest_framework.response import Response
from rest_framework.compat import is_authenticated

from settings import STATIC_ROOT
from chatroom.permissions import IsOwnerOrCreateOnly


# Create your views here.
def sendmail(request):
    from django.core.mail import send_mail
    send_mail('Subject here', 'Here is the message.', 'pigroom <1990815733@qq.com>', ['hi_youjiajia@163.com'])
    return HttpResponse(STATIC_ROOT)


from rest_framework import generics, mixins, authentication
from rest_framework.exceptions import ValidationError
from chatroom.models.user import UserProfile, User
from chatroom.serializer.user import OwnerProfileSerializer, OwnerChangeProfileSerializer, UserSerializer


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

    def get(self, request, *args, **kwargs):
        if request.user and is_authenticated(request.user):
            print request.user.profile
            userPro = request.user.profile
            serializer = self.get_serializer(userPro)
            return Response(serializer.data)
        return Response("")

    def post(self, request, *args, **kwargs):
        kwargs['context'] = self.get_serializer_context()
        serializer = UserSerializer(data=request.data, *args, **kwargs)
        if 'email' not in request.data:
            raise ValidationError({"email": ["This field is required."]})
        email = request.data['email']
        u = User.objects.filter(email=email).count()
        if u:
            raise ValidationError({"email": ["A user with that email already exists."]})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        request.data.appendlist('user', user.id)
        return self.create(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)
