from rest_framework import generics, permissions

from apps.user.serializers import FullUserInfoSerializer


class DefaultDashboardView(generics.RetrieveAPIView):
    """
    Default dashboard view

    Returns:
        - user_info
    """

    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = FullUserInfoSerializer

    def get_object(self):
        return self.request.user
