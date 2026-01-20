import re

from django.conf import settings
from django.db.models import Q
from django.db.models.functions import Now
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .models import User
from .validators import validate_user_password


class ChangePasswordSerializer(serializers.ModelSerializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(
        write_only=True, validators=[validate_user_password])

    class Meta:
        model = User
        fields = (
            'old_password',
            'new_password',
        )


class ChangeEmailSerializer(serializers.Serializer):
    password = serializers.CharField()
    new_email = serializers.EmailField()

    def validate(self, data):
        if not self.context['request'].user.check_password(data['password']):
            raise serializers.ValidationError(
                {'detail': _("Current password is entered incorrectly")}
            )
        if self.context['request'].user.email == data['new_email'].lower():
            raise serializers.ValidationError(
                {'detail': _("You already have this email address. Kindly try another one!")}
            )
        if User.objects.filter(email=data['new_email'].lower()).count() > 0:
            # Already exists user with such email
            msg = f'User with {data["new_email"]} already exists on the website. ' \
                  f'Please try another email address or contact the user.'
            raise serializers.ValidationError({'detail': str(msg)})

        return data

    class Meta:
        fields = ('password', 'new_email')


class UserSocialAccountSerializer(serializers.ModelSerializer):
    facebook = serializers.CharField(required=False, source='facebook_user_id')
    apple = serializers.CharField(required=False, source='apple_user_id')
    google = serializers.CharField(required=False, source='google_user_id')

    class Meta:
        model = User
        fields = ('facebook', 'apple', 'google')


class FullUserInfoSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(read_only=True)
    role = serializers.SerializerMethodField()
    accounts = serializers.SerializerMethodField()
    password_created = serializers.SerializerMethodField()
    email_added = serializers.SerializerMethodField()

    def get_role(self, obj):
        return {"id": obj.role, "name": dict(User.ROLE_CHOICES)[obj.role]}

    def get_password_created(self, obj):
        return not obj.check_password(settings.DEFAULT_PASSWORD)

    def get_email_added(self, obj):
        return not bool(re.match('\d+@temporary.com.uk$', obj.email))

    def get_accounts(self, obj):
        return UserSocialAccountSerializer(obj, context={'request': self.context.get('request')}).data

    def update(self, instance, validated_data):
        return super(FullUserInfoSerializer, self).update(instance, validated_data)

    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'role', 'accounts', 'email_added', 'password_created',
                  'created')
