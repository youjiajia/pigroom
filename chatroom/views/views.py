# coding: utf-8
from rest_framework.compat import is_authenticated
from chatroom.permissions import IsOwnerOrCreateOnly
from rest_framework import generics, mixins, authentication
from rest_framework.exceptions import ValidationError
from chatroom.models.user import UserProfile, User
from chatroom.base import const
from chatroom.serializer.user import OwnerProfileSerializer, OwnerChangeProfileSerializer, UserSerializer
from django.core.mail import EmailMultiAlternatives
from rest_framework.response import Response
from django.template import Context, loader
import settings as ST


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
        data = self.create(request, *args, **kwargs)

        # send verify email
        try:
            verify_url = "www.baidu.com"
            email_template_name = 'verify_email.html'
            t = loader.get_template(email_template_name)
            context = {
                'email': email,
                'verify_url': verify_url,
            }
            html_content = t.render(Context(context))
            subject = const.VERIFY
            msg = EmailMultiAlternatives(subject, html_content, ST.EMAIL_FROM, [email])
            msg.attach_alternative(html_content, "text/html")

            #TODO 有效期

            msg.send()
        except:
            raise ValidationError({"email": ["send email failure"]})
        return data

    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)
