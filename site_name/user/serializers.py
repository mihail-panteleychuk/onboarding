from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from subscription.constants import STATUS_PAID, STATUS_PAID_CANCELED, STATUS_TRIAL
from subscription.serializers import SubscriptionSerializer

from .models import (BillingAddress, Country, User, CompanyDetails)
# from payments.serializers import CardSerializer
from .validators import validate_user_password
from django.conf import settings
import re
from .utils import detect_country_by_ip
# from payments.utils import update_customer_billing_info
from django.db.models import Q
from django.db.models.functions import Now


class CountrySerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=False)
    id = serializers.IntegerField()

    class Meta:
        model = Country
        exclude = ('state',)


class CountryListSerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=False)
    id = serializers.IntegerField()

    class Meta:
        model = Country
        fields = "__all__"


class ShortCountrySerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=False)
    id = serializers.IntegerField()
    class Meta:
        model = Country
        fields = ('id', 'name')


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
            raise serializers.ValidationError(_("Current password is entered incorrectly"))
        if self.context['request'].user.email == data['new_email'].lower():
            raise serializers.ValidationError(_("You already have this email address. Kindly try another one!"))
        if User.objects.filter(email=data['new_email'].lower()).count() > 0:
            # Already exists user with such email
            raise serializers.ValidationError(_("This email already exists. Kindly try another one"))

        return data

    class Meta:
        fields = ('password', 'new_email')

#! maybe not needed
class BillingInfoSerializer(serializers.ModelSerializer):

    class Meta:
        model = BillingAddress
        fields = "__all__"
        extra_kwargs = {
            'user': {'read_only': True},
        }

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['user'] = user
        return super().create(validated_data)



class LanguageSerializer(serializers.Serializer):
    name = serializers.SerializerMethodField()
    value = serializers.SerializerMethodField()

    class Meta:
        fields = ('name', 'value')

    def get_name(self, obj):
        return obj[1]

    def get_value(self, obj):
        return obj[0]



class FullBillingInfoSerializer(serializers.ModelSerializer):
    country = CountrySerializer(required=False)
    address = serializers.CharField(required=False, allow_null=True)
    city = serializers.CharField(required=False, allow_null=True)
    postal_code = serializers.CharField(required=False, allow_null=True)
    state = serializers.CharField(required=False, allow_null=True)
    phone_code  = CountrySerializer(required=False, allow_null=True)
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    class Meta:
        model = BillingAddress
        exclude = ('user', 'updated', )

    def to_representation(self, instance, *args, **kwargs):
        data = super(FullBillingInfoSerializer, self).to_representation(instance, *args, **kwargs)
        by_ip = detect_country_by_ip(self.context['request'])
        if not data['phone_code']:
            data['phone_code'] = CountrySerializer(by_ip).data
        if not data['country']:
            data['country'] = CountrySerializer(by_ip).data

        return data

    def update(self, instance, validated_data):
        c = Country.objects.filter(**validated_data.get('country', {"id": 2321533313})).first()
        instance.country = c if c else instance.country
        phone_code = Country.objects.filter(**validated_data.get('phone_code', {"id": 2321533313})).first()
        instance.phone_code = phone_code if phone_code else instance.phone_code

        for field in ['phone','address','city','state','postal_code','first_name','last_name']:
            setattr(instance, field, validated_data.get(field) or getattr(instance, field))
        instance.save()
        return instance


class UserSocialAccountSerializer(serializers.ModelSerializer):
    facebook = serializers.CharField(required=False, source='facebook_user_id')
    apple = serializers.CharField(required=False, source='apple_user_id')
    google = serializers.CharField(required=False, source='google_user_id')

    class Meta:
        model = User
        fields = ('facebook', 'apple', 'google')


class CompanyDetailsSerializer(serializers.ModelSerializer):
    # FullUserInfoSerializer
    country = ShortCountrySerializer(required=True)
    name = serializers.CharField(max_length=128)
    city = serializers.CharField(max_length=128)
    state = serializers.CharField(max_length=128, required=False, allow_null=True)
    postal_code = serializers.CharField(max_length=128)
    address_line_1 = serializers.CharField(max_length=128)
    address_line_2 = serializers.CharField(max_length=128, required=False, allow_null=True)
    VAT = serializers.CharField(max_length=128, required=False, allow_null=True)

    class Meta:
        model = CompanyDetails
        exclude = ('created', 'updated', 'id', 'user')

    def update(self, instance, validated_data):
        country = Country.objects.filter(id=validated_data.get('country', {}).get('id')).first()
        instance.country = country if country else instance.country

        instance.name = validated_data.get('name', instance.name)
        instance.city = validated_data.get('city', instance.city)
        instance.state = validated_data.get('state', instance.state)
        instance.postal_code = validated_data.get('postal_code', instance.postal_code)
        instance.address_line_1 = validated_data.get('address_line_1', instance.address_line_1)
        instance.address_line_2 = validated_data.get('address_line_2', instance.address_line_2)
        instance.VAT = validated_data.get('VAT', instance.VAT)

        # company_billing = update_customer_billing_info(instance, _type='company') # sync user billing to payment service
        # if isinstance(company_billing, dict):
        #     raise serializers.ValidationError(company_billing['message'])

        instance.save()
        return instance


class FullUserInfoSerializer(serializers.ModelSerializer):
    billing_info = FullBillingInfoSerializer(source='user_billing', allow_null=True, required=False)
    email = serializers.EmailField(read_only=True)
    onboarding_finished = serializers.BooleanField(read_only=True)
    accounts = serializers.SerializerMethodField()
    email_added = serializers.SerializerMethodField()
    password_created = serializers.SerializerMethodField()
    company = CompanyDetailsSerializer(allow_null=True, required=False)
    role = serializers.SerializerMethodField()
    subscription = serializers.SerializerMethodField()
    # card = serializers.SerializerMethodField()


    # def get_card(self, obj):
    #     card = obj.cards.filter(active=True).select_related('billing', 'billing__country').first()

    #     return CardSerializer(card, context=self.context).data if card else None

    def get_subscription(self, obj):
        # # return SubscriptionSerializer(
        # #     obj.subscriptions.filter(Q(expire_date__gt=Now()) | Q(next_payment_date__gt=Now()))\
        # #         .filter(status__in=[STATUS_PAID, STATUS_PAID_CANCELED, STATUS_TRIAL])\
        # #             .select_related(
        # #                 'plan', 'scheduled_plan', 'discount', 'user', 'category__category_timer'
        # #             )
        # #         ).data
        return {}

    def get_role(self, obj):
        return {"id": obj.role, "name": dict(User.ROLE_CHOICES)[obj.role]}


    def to_representation(self, instance, *args, **kwargs):
        data = super(FullUserInfoSerializer, self).to_representation(instance, *args, **kwargs)
        phone_info = detect_country_by_ip(self.context['request'])
        phone_info_data = CountrySerializer(phone_info).data
        if not data['billing_info']:
            if phone_info:
                data['billing_info'] = {
                    "phone_code": phone_info_data,
                    "country": phone_info_data
                }
        else:
            data['billing_info']['phone_code'] = phone_info_data if not data['billing_info']['phone_code'] else data['billing_info']['phone_code']
            data['billing_info']['country'] = phone_info_data if not data['billing_info']['country'] else data['billing_info']['country']

        return data

    def get_password_created(self, obj):
        return not obj.check_password(settings.DEFAULT_PASSWORD)

    def get_email_added(self, obj):
        return not bool(re.match('\d+@temporary.com.uk$', obj.email))

    def get_accounts(self, obj):
        return UserSocialAccountSerializer(obj, context={'request': self.context.get('request')}).data

    def update(self, instance, validated_data):
        instance.user_billing = instance.user_billing if hasattr(instance, 'user_billing') else BillingAddress(user=instance)
        if 'user_billing' in validated_data or 'billing_info' in validated_data:
            s = FullBillingInfoSerializer(instance.user_billing, data=validated_data.pop('user_billing', validated_data.pop('billing_info', None)))
            s.is_valid()
            s.save()

        if 'company' in validated_data:
            instance.company = instance.company if hasattr(instance, 'company') else CompanyDetails()
            s = CompanyDetailsSerializer(instance.company, data=validated_data.pop('company'))
            s.is_valid()
            s.save()
        super(FullUserInfoSerializer, self).update(instance, validated_data)
        return instance

    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'language', 'avatar',
                  'billing_info', 'company', 'accounts', 'subscription', "role",
                  'payment_service_user_id', 'onboarding_finished', 'email_added',
                  'created', "password_created",)
                #   'card',


class SettingsSerializer(serializers.Serializer):
    language_list = serializers.SerializerMethodField()
    country_list = serializers.SerializerMethodField()

    class Meta:
        fields=('language_list', 'country_list')

    def get_language_list(self, obj):
        return LanguageSerializer(settings.LANGUAGES, many=True).data


    def get_country_list(self, obj):
        return CountryListSerializer(Country.objects.all().order_by('name'), context={'request': self.context.get('request')}, many=True).data


