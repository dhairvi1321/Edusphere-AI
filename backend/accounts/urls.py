from django.urls import path
from .views import RegisterView, EmailTokenObtainView, TokenRefreshView, GoogleLoginView, MeView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', EmailTokenObtainView.as_view(), name='login'),
    path('google/', GoogleLoginView.as_view(), name='google_login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', MeView.as_view(), name='me'),
]
