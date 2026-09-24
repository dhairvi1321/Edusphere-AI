import jwt
import datetime
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from .models import User
from .serializers import RegisterSerializer


def make_tokens(user):
    now = datetime.datetime.now(datetime.timezone.utc)
    access_payload = {
        'user_id': str(user.id),
        'exp': now + datetime.timedelta(days=1),
        'iat': now,
        'token_type': 'access',
    }
    refresh_payload = {
        'user_id': str(user.id),
        'exp': now + datetime.timedelta(days=7),
        'iat': now,
        'token_type': 'refresh',
    }
    access = jwt.encode(access_payload, settings.SECRET_KEY, algorithm='HS256')
    refresh = jwt.encode(refresh_payload, settings.SECRET_KEY, algorithm='HS256')
    return access, refresh


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response({'detail': 'Account created.'}, status=status.HTTP_201_CREATED)


class EmailTokenObtainView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        identifier = request.data.get('username') or request.data.get('email', '')
        password = request.data.get('password', '')

        if not identifier or not password:
            return Response({'detail': 'Email and password are required.'}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects(email=identifier).first() or User.objects(username=identifier).first()

        if not user or not user.check_password(password):
            return Response({'detail': 'Invalid email or password.'}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return Response({'detail': 'Account is disabled.'}, status=status.HTTP_403_FORBIDDEN)

        access, refresh = make_tokens(user)
        return Response({'access': access, 'refresh': refresh})


class TokenRefreshView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        token = request.data.get('refresh', '')
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return Response({'detail': 'Refresh token expired.'}, status=status.HTTP_401_UNAUTHORIZED)
        except jwt.InvalidTokenError:
            return Response({'detail': 'Invalid token.'}, status=status.HTTP_401_UNAUTHORIZED)

        if payload.get('token_type') != 'refresh':
            return Response({'detail': 'Invalid token type.'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            user = User.objects.get(id=payload['user_id'])
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_401_UNAUTHORIZED)

        access, refresh = make_tokens(user)
        return Response({'access': access, 'refresh': refresh})


class GoogleLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        credential = request.data.get('credential', '')
        if not credential:
            return Response({'detail': 'Google credential is required.'}, status=status.HTTP_400_BAD_REQUEST)

        client_id = settings.GOOGLE_CLIENT_ID
        if not client_id:
            return Response({'detail': 'Google login is not configured.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            info = id_token.verify_oauth2_token(credential, google_requests.Request(), client_id)
        except ValueError as e:
            return Response({'detail': f'Invalid Google token: {e}'}, status=status.HTTP_400_BAD_REQUEST)

        email = info.get('email', '')
        if not email:
            return Response({'detail': 'Google account has no email.'}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects(email=email).first()
        created = False
        if not user:
            name = info.get('name', '')
            user = User(
                username=email,
                email=email,
                first_name=info.get('given_name', name.split()[0] if name else ''),
                last_name=info.get('family_name', ''),
                google_user=True,
            )
            user.save()
            created = True

        access, refresh = make_tokens(user)
        return Response({'access': access, 'refresh': refresh, 'created': created})


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        u = request.user
        return Response({
            'id': str(u.id),
            'name': u.get_full_name() or u.first_name or u.username,
            'email': u.email or u.username,
        })
