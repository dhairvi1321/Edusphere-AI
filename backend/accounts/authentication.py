import jwt
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import User


class MongoUserWrapper:
    """Wraps a mongoengine User to satisfy DRF's is_authenticated check."""
    def __init__(self, user):
        self._user = user

    def __getattr__(self, name):
        return getattr(self._user, name)

    @property
    def is_authenticated(self):
        return True

    @property
    def pk(self):
        return str(self._user.id)


class MongoJWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        header = request.headers.get('Authorization', '')
        if not header.startswith('Bearer '):
            return None

        token = header.split(' ', 1)[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('Token expired.')
        except jwt.InvalidTokenError:
            raise AuthenticationFailed('Invalid token.')

        user_id = payload.get('user_id')
        if not user_id:
            raise AuthenticationFailed('Invalid token payload.')

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise AuthenticationFailed('User not found.')

        return (MongoUserWrapper(user), token)
