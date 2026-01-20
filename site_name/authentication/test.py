from authentication.utils import *
from authentication.views import *
from django.conf import settings
from django.test import Client, TestCase
from django.urls import include, path
from model_bakery import baker
from rest_framework.test import (
    APIRequestFactory,
    APITestCase,
    URLPatternsTestCase,
    force_authenticate,
)
from user.models import ConfirmCode


class BaseViewTest(TestCase):
    def setUp(self):
        self.client = Client()


class CustomTokenObtainPairViewTest(APITestCase, URLPatternsTestCase):
    urlpatterns = [
        path("api/auth/", include("authentication.urls")),
    ]

    def setUp(self):
        super().setUp()
        self.user = baker.make("user.User")
        self.password = "12351994"
        self.user.set_password(self.password)
        self.user.save()

    def test_user_auth_success(self):
        data = {"email": self.user.email, "password": self.password}
        api_request = APIRequestFactory().post("", data=data)
        view = CustomTokenObtainPairView.as_view()
        resp = view(api_request)

        self.assertEqual(resp.status_code, 200)
        resp_keys = ["refresh", "access", "user"]
        keys_in_resp = [key in resp.data.keys() for key in resp_keys]
        self.assertTrue(all(keys_in_resp))

    def test_user_auth_invalid_pass(self):
        data = {"email": self.user.email, "password": "self.password"}
        api_request = APIRequestFactory().post("", data=data)
        view = CustomTokenObtainPairView.as_view()
        resp = view(api_request)

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.data["message"]["detail"], "The email or password you entered is incorrect."
        )


class CustomTokenRefreshViewTest(APITestCase, URLPatternsTestCase):
    urlpatterns = [
        path("api/auth/", include("authentication.urls")),
    ]

    def setUp(self):
        super().setUp()
        self.user = baker.make("user.User")
        self.password = "12351994"
        self.user.set_password(self.password)
        self.user.save()

    def get_refresh_token(self):
        data = {"email": self.user.email, "password": self.password}
        api_request = APIRequestFactory().post("", data=data)
        view = CustomTokenObtainPairView.as_view()
        resp = view(api_request)
        return resp.data["refresh"]

    def test_post_refresh_success(self):
        refresh_token = self.get_refresh_token()
        data = {
            "refresh": refresh_token,
        }
        api_request = APIRequestFactory().post("", data=data)
        view = CustomTokenRefreshView.as_view()
        resp = view(api_request)

        self.assertEqual(resp.status_code, 200)
        resp_keys = ["refresh", "access", "user"]
        self.assertTrue(all([key in resp.data.keys() for key in resp_keys]))


class ChangeUserEmailTest(APITestCase, URLPatternsTestCase):
    urlpatterns = [
        path("api/auth/", include("authentication.urls")),
    ]

    def setUp(self):
        super().setUp()
        self.new_email = "vitalik_t+1@dataforest.ai"
        self.existing_email = "vitalik_t@dataforest.ai"

        self.users = baker.make("user.User", _quantity=2)
        self.another_user = self.users[1]
        self.another_user.email = self.existing_email
        self.another_user.save()

        self.user = self.users[0]
        self.password = "12351994"
        self.user.set_password(self.password)
        self.user.save()

    def test_change_success(self):
        data = {"email": self.user.email, "new_email": self.new_email}
        api_request = APIRequestFactory().post("", data=data)
        view = ChangeUserEmail.as_view()
        resp = view(api_request)

        self.assertEqual(resp.status_code, 200)

    def test_change_old_email_not_passed(self):
        data = {"new_email": self.new_email}
        api_request = APIRequestFactory().post("", data=data)
        view = ChangeUserEmail.as_view()
        resp = view(api_request)

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["message"]["detail"], "Old user email not providen.")

    def test_change_old_email_is_invalid(self):
        data = {"email": self.user.email + "123", "new_email": self.new_email}
        api_request = APIRequestFactory().post("", data=data)
        view = ChangeUserEmail.as_view()
        resp = view(api_request)

        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.data["message"]["detail"], "Not found.")

    def test_change_email_new_email_already_exists(self):
        data = {"email": self.user.email, "new_email": self.existing_email}
        api_request = APIRequestFactory().post("", data=data)
        view = ChangeUserEmail.as_view()
        resp = view(api_request)

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["message"]["detail"], "This email already exists.")

    def test_change_email_new_email_not_providen(self):
        data = {
            "email": self.user.email,
        }
        api_request = APIRequestFactory().post("", data=data)
        view = ChangeUserEmail.as_view()
        resp = view(api_request)

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["message"]["detail"], "New user email not providen.")

    def test_change_email_already_confirmed(self):
        self.user.email_confirmed = True
        self.user.save()
        data = {"email": self.user.email, "new_email": self.new_email}
        api_request = APIRequestFactory().post("", data=data)
        view = ChangeUserEmail.as_view()
        resp = view(api_request)

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["message"]["detail"], "User email is already verified.")


class SendConfirmationEmailTest(APITestCase, URLPatternsTestCase):
    urlpatterns = [
        path("api/auth/", include("authentication.urls")),
    ]

    def setUp(self):
        super().setUp()
        self.user_models = baker.make("user.User", _quantity=2)

        self.new_email = "vitalik_t@dataforest.ai"
        self.new_email_2 = "vitalik_t+1@dataforest.ai"
        self.password = "12351994"
        self.incorrect_password = "12351994"
        self.first_name = "Vitalik"
        self.last_name = "Tust"

        self.__prepare()

    def __prepare(self):
        self.user = self.user_models[0]
        self.other_user = self.user_models[1]

        self.user.set_password(self.password)
        self.user.first_name = self.first_name
        self.user.last_name = self.last_name
        self.user.save()

        self.other_user.set_password(self.password)
        self.other_user.email = self.new_email_2
        self.other_user.save()

    def __check_if_data_is_full_user_info(self, data):
        data_keys = [
            "id",
            "first_name",
            "last_name",
            "email",
            "language",
            "avatar",
            "billing_info",
            "created",
            "company",
            "accounts",
            "subscription",
            "role",
            "payment_service_user_id",
            "onboarding_finished",
            "email_added",
            "created",
            "password_created",
        ]
        self.assertTrue(all([key in data_keys for key in data.keys()]))

    def __send_success_email_change_anonymous(self):
        data = {
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.new_email,
        }
        api_request = APIRequestFactory().post("", data=data)
        detail_view = SendConfirmationEmail.as_view()
        resp = detail_view(api_request)
        return resp

    def __send_success_email_change_authorized(self):
        data = {
            "email": self.new_email,
        }
        api_request = APIRequestFactory().post("", data=data)
        detail_view = SendConfirmationEmail.as_view()
        force_authenticate(api_request, user=self.user)
        resp = detail_view(api_request)
        return resp

    def test_send_email_success(self):
        resp = self.__send_success_email_change_authorized()

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, "Confirmation email was sent")

    def test_send_email_address_is_invalid(self):
        self.new_email = "slkdnjsdf"
        resp = self.__send_success_email_change_anonymous()

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["message"]["detail"], "Please provide a valid email address")

    def test_send_email_name_is_invalid(self):
        self.first_name = ""
        resp = self.__send_success_email_change_anonymous()

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.data["message"]["detail"], "Please provide first name, last name and email"
        )

    def test_send_email_already_exists(self):
        self.new_email = self.new_email_2
        resp = self.__send_success_email_change_anonymous()

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["message"]["detail"], "This email already exists.")

    def test_send_email_success_anon(self):
        self.new_email = self.new_email
        resp = self.__send_success_email_change_anonymous()

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, "Confirmation email was sent")

    def test_send_email_success_2(self):
        self.other_user.is_active = False
        self.other_user.save()
        self.new_email = self.new_email_2
        resp = self.__send_success_email_change_anonymous()

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, "Confirmation email was sent")

    def test_send_email_invalid_address(self):
        self.new_email = "asdgkjjdbg"
        resp = self.__send_success_email_change_authorized()

        self.assertEqual(resp.status_code, 400)
        self.assertIsInstance(resp.data, dict)
        self.assertEqual(resp.data["message"]["detail"], "Please provide a valid email address")

    def test_confirm_code_not_passed(self):
        api_request = APIRequestFactory().get("")
        detail_view = SendConfirmationEmail.as_view()
        force_authenticate(api_request, user=self.user)
        resp = detail_view(api_request)

        self.assertEqual(resp.status_code, 400)
        self.assertIsInstance(resp.data, dict)
        self.assertEqual(resp.data["message"]["detail"], "provide digital code")

    def test_confirm_code_not_digit(self):
        api_request = APIRequestFactory().get("", {"code": "asd"})
        detail_view = SendConfirmationEmail.as_view()
        force_authenticate(api_request, user=self.user)
        resp = detail_view(api_request)

        self.assertEqual(resp.status_code, 400)
        self.assertIsInstance(resp.data, dict)
        self.assertEqual(resp.data["message"]["detail"], "provide digital code")

    def test_confirm_code_is_invalid(self):
        api_request = APIRequestFactory().get("", {"code": "12351239834"})
        detail_view = SendConfirmationEmail.as_view()
        force_authenticate(api_request, user=self.user)
        resp = detail_view(api_request)

        self.assertEqual(resp.status_code, 400)
        self.assertIsInstance(resp.data, dict)
        self.assertEqual(
            resp.data["message"]["detail"],
            "Email not confirmed. Confirmation code is expired or does not exist.",
        )


class ForgotPasswordViewTest(APITestCase, URLPatternsTestCase):
    urlpatterns = [
        path("api/auth/", include("authentication.urls")),
    ]

    def setUp(self):
        super().setUp()
        self.email = "vitalik_t@dataforest.ai"
        self.invalid_email = "asdasfafas"
        self.existing_email = "vitalik_t+1@dataforest.ai"
        self.non_existing_email = "vitalik_t+2@dataforest.ai"

        self.user_models = baker.make("user.User", _quantity=2)
        self.user = self.user_models[0]
        self.user.email = self.email

        self.user.save()

        self.other_user = self.user_models[1]
        self.other_user.email = self.existing_email
        self.other_user.save()

    def __send_post_request_forgot_password(self, data):
        api_request = APIRequestFactory().post("", data=data)
        detail_view = ForgotPasswordView.as_view()
        resp = detail_view(api_request)
        return resp

    def test_post_invalid_email(self):
        data = {
            "email": self.invalid_email,
        }
        resp = self.__send_post_request_forgot_password(data)

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["message"]["detail"], "Please provide a valid email address")

    def test_post_not_existing_email(self):
        data = {"email": self.non_existing_email}
        resp = self.__send_post_request_forgot_password(data)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["message"]["detail"], "The email you entered is incorrect")

    def test_post_success_authenticated(self):
        data = {
            "email": self.email,
        }
        api_request = APIRequestFactory().post("", data=data)
        detail_view = ForgotPasswordView.as_view()
        force_authenticate(api_request, user=self.user)
        resp = detail_view(api_request)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["message"]["detail"], "Email with confirmation code was sent")

    def test_post_success(self):
        data = {
            "email": self.email,
        }
        resp = self.__send_post_request_forgot_password(data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, "Email with confirmation code was sent")

    def __send_success_email(self):
        data = {
            "email": self.email,
        }
        resp = self.__send_post_request_forgot_password(data)
        return resp

    def __send_get_request_forgot_password(self, data):
        api_request = APIRequestFactory().get("", data)
        detail_view = ForgotPasswordView.as_view()
        resp = detail_view(api_request)
        return resp

    def __send_get_request_forgot_password_with_auth(self, data, auth_user):
        api_request = APIRequestFactory().get("", data)
        detail_view = ForgotPasswordView.as_view()
        force_authenticate(api_request, user=auth_user)
        resp = detail_view(api_request)
        return resp

    def test_get_incorrect_code(self):
        self.__send_success_email()
        data = {}
        resp = self.__send_get_request_forgot_password(data)

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.data["message"]["detail"], "The code you entered is incorrect, please try again"
        )

    def test_get_correct_code(self):
        self.__send_success_email()
        code = ConfirmCode.objects.filter(user=self.user).first()
        data = {"code": code.code}
        resp = self.__send_get_request_forgot_password(data)

        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.data, dict)
        resp_keys = ["refresh", "access", "user"]
        self.assertTrue(all([key in resp.data.keys() for key in resp_keys]))

    def test_get_correct_code_with_auth(self):
        self.__send_success_email()
        code = ConfirmCode.objects.filter(user=self.user).first()
        data = {"code": code.code}
        resp = self.__send_get_request_forgot_password_with_auth(data, self.user)

        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.data, dict)
        self.assertEqual(resp.data["message"]["detail"], "Code is valid.")

    def test_get_correct_code_with_invalid_auth(self):
        self.__send_success_email()
        code = ConfirmCode.objects.filter(user=self.user).first()
        data = {"code": code.code}
        resp = self.__send_get_request_forgot_password_with_auth(data, self.other_user)

        self.assertEqual(resp.status_code, 400)
        self.assertIsInstance(resp.data, dict)
        self.assertEqual(
            resp.data["message"]["detail"], "The code you entered is incorrect, please try again"
        )


class TempEmailGeneratingTest(TestCase):
    def setUp(self):
        super().setUp()

    def test_generating(self):
        temp_email = generate_temp_email()
        self.assertTrue(temp_email.endswith("temporary.com.uk"))

        timestamp = int(temp_email.split("@")[0])
        self.assertTrue(timestamp < now().timestamp())


class SocialAccountDeleteTest(APITestCase, URLPatternsTestCase):
    urlpatterns = [
        path("api/auth/", include("authentication.urls")),
    ]

    social_views = {
        "facebook": FacebookTokenView,
        "apple": AppleTokenView,
        "google": GoogleTokenView,
    }

    def setUp(self):
        super().setUp()
        self.email = "vitalik_t@dataforest.ai"
        self.password = "12351994"
        self.user = baker.make("user.User") if not hasattr(self, "user") else self.user
        self.user.email = self.email
        self.user.set_password(settings.DEFAULT_PASSWORD)
        self.user.facebook_user_id = self.email
        self.user.apple_user_id = self.email
        self.user.google_user_id = self.email

        self.user.save()

    def __send_delete_request(self, social_view="google", auth_user=None):
        view = self.social_views[social_view]

        api_request = APIRequestFactory().delete("")
        detail_view = view.as_view()
        if auth_user:
            force_authenticate(api_request, user=self.user)

        resp = detail_view(api_request)
        return resp

    def test_delete_401_facebook(self):
        resp = self.__send_delete_request("facebook")

        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.data["message"]["detail"], "Not Authenticated")

    def test_delete_401_google(self):
        resp = self.__send_delete_request("google")

        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.data["message"]["detail"], "Not Authenticated")

    def test_delete_401_apple(self):
        resp = self.__send_delete_request("apple")

        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.data["message"]["detail"], "Not Authenticated")

    def test_delete_google_as_last(self):
        self.user.google_user_id = self.email
        self.user.apple_user_id = None
        self.user.facebook_user_id = None
        self.user.save()
        resp = self.__send_delete_request("google", auth_user=self.user)

        self.assertEqual(resp.status_code, 400)

    def test_delete_facebook_as_last(self):
        self.user.facebook_user_id = self.email
        self.user.apple_user_id = None
        self.user.google_user_id = None
        self.user.save()
        resp = self.__send_delete_request("facebook", auth_user=self.user)

        self.assertEqual(resp.status_code, 400)

    def test_delete_apple_as_last(self):
        self.user.apple_user_id = self.email
        self.user.google_user_id = None
        self.user.facebook_user_id = None
        self.user.save()
        resp = self.__send_delete_request("apple", auth_user=self.user)

        self.assertEqual(resp.status_code, 400)

    def __check_if_data_is_full_user_info(self, data):
        data_keys = [
            "id",
            "first_name",
            "last_name",
            "email",
            "language",
            "avatar",
            "billing_info",
            "created",
            "company",
            "accounts",
            "subscription",
            "role",
            "payment_service_user_id",
            "onboarding_finished",
            "email_added",
            "created",
            "password_created",
        ]
        self.assertTrue(all([key in data_keys for key in data.keys()]))

    def test_delete_apple_success(self):
        self.setUp()
        resp = self.__send_delete_request("apple", auth_user=self.user)

        self.assertEqual(resp.status_code, 200)
        self.__check_if_data_is_full_user_info(resp.data)

    def test_delete_facebook_success(self):
        self.setUp()
        resp = self.__send_delete_request("facebook", auth_user=self.user)

        self.assertEqual(resp.status_code, 200)
        self.__check_if_data_is_full_user_info(resp.data)

    def test_delete_google_success(self):
        self.setUp()
        resp = self.__send_delete_request("google", auth_user=self.user)

        self.assertEqual(resp.status_code, 200)
        self.__check_if_data_is_full_user_info(resp.data)
