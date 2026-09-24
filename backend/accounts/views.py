import os
from django.contrib.auth.models import User
from django.conf import settings
from rest_framework import generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from .serializers import RegisterSerializer


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class EmailTokenObtainView(APIView):
    """Login with email (or username) + password, returns JWT pair."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        identifier = request.data.get('username') or request.data.get('email', '')
        password = request.data.get('password', '')

        if not identifier or not password:
            return Response({'detail': 'Email and password are required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Try email lookup first, fall back to username
        user = None
        if '@' in identifier:
            user = User.objects.filter(email=identifier).first()
        if not user:
            user = User.objects.filter(username=identifier).first()

        if not user or not user.check_password(password):
            return Response({'detail': 'Invalid email or password.'}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return Response({'detail': 'Account is disabled.'}, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        })


class GoogleLoginView(APIView):
    """Verify a Google ID token and return JWT pair, creating user if needed."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        credential = request.data.get('credential', '')
        if not credential:
            return Response({'detail': 'Google credential is required.'}, status=status.HTTP_400_BAD_REQUEST)

        client_id = settings.GOOGLE_CLIENT_ID
        if not client_id:
            return Response({'detail': 'Google login is not configured on the server.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            info = id_token.verify_oauth2_token(credential, google_requests.Request(), client_id)
        except ValueError as e:
            return Response({'detail': f'Invalid Google token: {e}'}, status=status.HTTP_400_BAD_REQUEST)

        email = info.get('email', '')
        name = info.get('name', '')
        first_name = info.get('given_name', name.split()[0] if name else '')
        last_name = info.get('family_name', '')

        if not email:
            return Response({'detail': 'Google account has no email.'}, status=status.HTTP_400_BAD_REQUEST)

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': email,
                'first_name': first_name,
                'last_name': last_name,
            }
        )
        if created:
            user.set_unusable_password()
            user.save()

        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'created': created,
        })


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        u = request.user
        return Response({
            'id': u.id,
            'name': u.get_full_name() or u.first_name or u.username,
            'email': u.email or u.username,
        })
