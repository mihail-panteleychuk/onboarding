from .models import *
from rest_framework import serializers
from django.contrib.auth import get_user_model
from user.validators import validate_user_password, role_validator


class BaseAdminPanelUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ('id', 'avatar', 'first_name', 'last_name', 'email', 'role', 'password',)
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def create(self, validated_data):
        if 'get_role_object' in self._validated_data: self._validated_data.update({'role': self._validated_data.pop('get_role_object')})
        return super(BaseAdminPanelUserSerializer, self).create(validated_data)

    def update(self, instance, validated_data):
        if 'get_role_object' in self._validated_data: self._validated_data.update({'role': self._validated_data.pop('get_role_object')})
        return super(BaseAdminPanelUserSerializer, self).update(instance, validated_data)


class AdminPanelUserUpdateSerializer(BaseAdminPanelUserSerializer):
    password = serializers.CharField(write_only=True, required=False, validators=[validate_user_password])
    role = serializers.JSONField(source='get_role_object', required=False, validators=[role_validator])


class AdminPanelUserCreateSerializer(BaseAdminPanelUserSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_user_password])
    role = serializers.JSONField(source='get_role_object',
                                 default=get_user_model().USER,
                                 validators=[role_validator])
