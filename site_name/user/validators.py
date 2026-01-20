from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework import serializers
from django.contrib.auth import get_user_model

__all__ = (
    'validate_user_password',
    'role_validator'
)


def validate_user_password(value):
    try:
        validate_password(value)
    except ValidationError as e:
        raise serializers.ValidationError(e.messages)
    # return value


def role_validator(value):
    if value not in dict(get_user_model().ROLE_CHOICES):
        raise serializers.ValidationError('Invalid value.')
