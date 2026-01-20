from django.urls import path
from rest_framework_simplejwt.views import TokenVerifyView

from .views import (
    AppleTokenView,
    ChangeUserEmail,
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    FacebookTokenView,
    ForgotPasswordView,
    GoogleTokenView,
    SendConfirmationEmail,
)

urlpatterns = [
    path("token/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("social/google/", GoogleTokenView.as_view(), name="token_google"),
    path("social/apple/", AppleTokenView.as_view(), name="token_google"),
    path("social/facebook/", FacebookTokenView.as_view(), name="token_facebook"),
    path("confirm-email/", SendConfirmationEmail.as_view(), name="confirm_email"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot_password"),
    path("change-email/", ChangeUserEmail.as_view(), name="confirm_email"),
]
