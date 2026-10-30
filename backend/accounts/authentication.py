import jwt
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import APIException, AuthenticationFailed
from pymongo.errors import PyMongoError
from mongoengine.errors import ValidationError as MongoValidationError
from .models import User


class MongoUnavailable(APIException):
    status_code = 503
    default_detail = 'User data is temporarily unavailable. Please try again.'
    default_code = 'database_unavailable'


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
    def authenticate_header(self, request):
        # Makes DRF return 401 (with a Bearer challenge) for missing/invalid
        # credentials instead of its default 403 for custom authenticators.
        return 'Bearer'

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
        if not user_id or payload.get('token_type') != 'access':
            raise AuthenticationFailed('Invalid token payload.')

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise AuthenticationFailed('User not found.')
        except MongoValidationError as exc:
            raise AuthenticationFailed('Invalid user identifier in token.') from exc
        except PyMongoError as exc:
            # MongoEngine queries run here before the view is called. Convert
            # temporary Atlas/network failures into a clear HTTP 503 response.
            raise MongoUnavailable() from exc

        return (MongoUserWrapper(user), token)
