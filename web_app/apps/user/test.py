from django.conf import settings
from django.test import Client, TestCase
from django.urls import include, path, reverse
from django.utils import timezone
from model_bakery import baker
from rest_framework.test import (
    APIRequestFactory,
    APITestCase,
    URLPatternsTestCase,
    force_authenticate,
)

from apps.core.tests import SkipStripeSignalsTestCase
from apps.user.views import ChangeUserEmail, ConfirmCode, CountryListView, UserViewSet


class TestUserStripe(SkipStripeSignalsTestCase):
    def setUp(self):
        self.models = baker.make("user.User")

    def test_str(self):
        self.assertEqual(str(self.models), self.models.email)

    def test_full_name(self):
        test_full_name = (
            f"{self.models.first_name or '' } {self.models.last_name or ''}"
            if any([self.models.first_name, self.models.last_name])
            else None
        )
        self.assertEqual(self.models.full_name, test_full_name)


class TestCountryStripe(SkipStripeSignalsTestCase):
    def setUp(self):
        self.models = baker.make("user.Country")

    def test_str(self):
        self.assertEqual(str(self.models), self.models.name)


# ===========================================================================================
# ======================================= Views Tests =======================================
# ===========================================================================================


class ViewTestStripe(SkipStripeSignalsTestCase):
    def setUp(self):
        self.client = Client()


class CountryListViewTestStripe(SkipStripeSignalsTestCase, APITestCase, URLPatternsTestCase):
    urlpatterns = [
        path("api/user/", include("apps.user.urls")),
    ]

    def setUp(self):
        super().setUp()
        self.country_model = baker.make("user.Country", _quantity=10)
        self.user_model = baker.make("user.User")

    def test_list_401(self):
        url = reverse("country-list")

        resp = self.client.get(url, format="json")
        self.assertEqual(resp.status_code, 401)

        # self.assertIsInstance(resp.json(), list)

    def test_list_success(self):
        url = reverse("country-list")
        self.client.force_authenticate(user=self.user_model)

        resp = self.client.get(url, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)
        self.assertEqual(len(resp.json()), len(self.country_model))

    def test_retrieve_success(self):
        api_request = APIRequestFactory().get("")
        detail_view = CountryListView.as_view({"get": "retrieve"})
        country_id = self.country_model[0].id
        force_authenticate(api_request, user=self.user_model)

        resp = detail_view(api_request, pk=country_id)
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.data, dict)
        self.assertEqual(resp.data["id"], country_id)
        self.assertEqual(resp.data["name"], self.country_model[0].name)


class UserViewSetTestStripe(SkipStripeSignalsTestCase, APITestCase, URLPatternsTestCase):
    urlpatterns = [
        path("api/user/", include("apps.user.urls")),
    ]

    def setUp(self):
        super().setUp()
        # self.country_model = baker.make('user.Country', _quantity=10)
        self.user_model = baker.make("user.User")

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
        self.assertTrue(all(key in data_keys for key in data.keys()))

    def test_retrieve_401(self):
        url = reverse("country-list")

        resp = self.client.get(url, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_retrieve_success(self):
        api_request = APIRequestFactory().get("")
        detail_view = UserViewSet.as_view({"get": "account"})
        force_authenticate(api_request, user=self.user_model)

        resp = detail_view(api_request)
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.data, dict)
        self.assertEqual(resp.data["id"], str(self.user_model.id))
        self.__check_if_data_is_full_user_info(resp.data)

    def test_update_user_name(self):
        old_name = self.user_model.first_name
        new_name = "Vitalik"
        api_request = APIRequestFactory().patch(
            "",
            data={"first_name": new_name},
            format=None,
            content_type=None,
        )
        detail_view = UserViewSet.as_view({"patch": "update_user", "put": "update_user"})
        force_authenticate(api_request, user=self.user_model)
        resp = detail_view(api_request)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["first_name"], new_name)
        self.assertNotEqual(resp.data["first_name"], old_name)
        self.__check_if_data_is_full_user_info(resp.data)

    def test_update_role_invalid(self):
        old_role = self.user_model.role
        new_role = 20
        api_request = APIRequestFactory().patch(
            "",
            data={"role": new_role},
            format=None,
            content_type=None,
        )
        detail_view = UserViewSet.as_view({"patch": "update_user", "put": "update_user"})
        force_authenticate(api_request, user=self.user_model)
        resp = detail_view(api_request)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["role"]["id"], old_role)
        self.assertNotEqual(resp.data["role"]["id"], new_role)

    def test_list_languages_action(self):
        api_request = APIRequestFactory().get("")
        detail_view = UserViewSet.as_view({"get": "list_languages"})
        force_authenticate(api_request, user=self.user_model)
        resp = detail_view(api_request)

        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.data, list)
        self.assertEqual(len(resp.data), len(settings.LANGUAGES))

    def test_set_language_success(self):
        old_language = self.user_model.language
        new_language = "de"
        api_request = APIRequestFactory().post("", data={"language": new_language})
        detail_view = UserViewSet.as_view({"post": "set_language"})
        force_authenticate(api_request, user=self.user_model)
        resp = detail_view(api_request)

        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.data, dict)
        self.assertNotEqual(resp.data["language"], old_language)
        self.assertEqual(resp.data["language"], new_language)
        self.__check_if_data_is_full_user_info(resp.data)

    def test_set_language(self):
        api_request = APIRequestFactory().post("", data={})
        detail_view = UserViewSet.as_view({"post": "set_language"})
        force_authenticate(api_request, user=self.user_model)
        resp = detail_view(api_request)

        self.assertEqual(resp.status_code, 400)
        self.assertIsInstance(resp.data, dict)
        self.assertEqual(
            resp.data["message"]["detail"],
            "Required field 'language' is not passed.",
        )

    def __update_password_to(self, password):
        api_request = APIRequestFactory().post("", data={"new_password": password})
        detail_view = UserViewSet.as_view({"post": "set_password"})
        force_authenticate(api_request, user=self.user_model)
        resp = detail_view(api_request)
        return resp

    def test_set_password_success(self):
        password = "12351994"
        resp = self.__update_password_to(password)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["message"]["detail"], "A password has been successfully set!")
        if settings.ONBOARDING_ENABLED:
            self.assertEqual(resp.data["onboarding_finished"], False)
        else:
            self.assertEqual(resp.data["onboarding_finished"], True)

    def test_set_password_not_active_account(self):
        password = "12351994"
        self.user_model.is_active = False
        self.user_model.save()
        resp = self.__update_password_to(password)

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["message"]["detail"], "User email is not confirmed.")

    def test_set_password_to_old_password(self):
        password = "12351994"
        resp = self.__update_password_to(password)
        resp = self.__update_password_to(password)

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["password"][0], "You already have this password")

    def test_set_password_to_invalid_password(self):
        password = "123"
        resp = self.__update_password_to(password)
        resp = self.__update_password_to(password)

        self.assertEqual(resp.status_code, 400)
        # self.assertEquals(resp.data['password'][0], 'You already have this password')

    def test_change_password_success(self):
        old_password = "12351994"
        new_password = "11111111"
        data = {"old_password": old_password, "new_password": new_password}
        self.__update_password_to(old_password)
        api_request = APIRequestFactory().put("", data=data)
        detail_view = UserViewSet.as_view({"put": "change_password"})
        force_authenticate(api_request, user=self.user_model)
        resp = detail_view(api_request)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["message"]["detail"], "Your password has successfully changed!")

    def test_change_password_serializer_failed(self):
        new_password = "11111111"
        data = {"new_password": new_password}
        # self.__update_password_to(old_password)
        api_request = APIRequestFactory().put("", data=data)
        detail_view = UserViewSet.as_view({"put": "change_password"})
        force_authenticate(api_request, user=self.user_model)
        resp = detail_view(api_request)

        self.assertEqual(resp.status_code, 400)

    def test_change_password_incorrect_current_pass(self):
        old_password = "12351994"
        self.__update_password_to(old_password)
        new_password = "11111111"
        data = {"old_password": new_password, "new_password": new_password}
        api_request = APIRequestFactory().put("", data=data)
        detail_view = UserViewSet.as_view({"put": "change_password"})
        force_authenticate(api_request, user=self.user_model)
        resp = detail_view(api_request)

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["message"]["detail"], "Current password is entered incorrectly")

    def test_change_password_the_same_new_pass(self):
        old_password = "12351994"
        self.__update_password_to(old_password)
        data = {"old_password": old_password, "new_password": old_password}
        api_request = APIRequestFactory().put("", data=data)
        detail_view = UserViewSet.as_view({"put": "change_password"})
        force_authenticate(api_request, user=self.user_model)
        resp = detail_view(api_request)

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["message"]["detail"], "You already have this password")


class ChangeUserEmailViewTestStripe(SkipStripeSignalsTestCase, APITestCase, URLPatternsTestCase):
    urlpatterns = [
        path("api/user/", include("apps.user.urls")),
    ]

    def setUp(self):
        super().setUp()
        self.user_models = baker.make("user.User", _quantity=2)

        self.new_email = "vitalik_t@dataforest.ai"
        self.new_email_2 = "vitalik_t+1@dataforest.ai"
        self.password = "12351994"
        self.incorrect_password = "12351994"

        self.__prepare()

    def __prepare(self):
        self.user = self.user_models[0]
        self.other_user = self.user_models[1]

        self.user.set_password(self.password)
        self.user.save()

        self.other_user.set_password(self.password)
        self.other_user.email = self.new_email_2
        self.other_user.save()

    def __send_success_email_change(self):
        data = {
            "password": self.password,
            "new_email": self.new_email,
        }
        api_request = APIRequestFactory().post("", data=data)
        detail_view = ChangeUserEmail.as_view()
        force_authenticate(api_request, user=self.user)
        resp = detail_view(api_request)
        return resp

    def test_send_message_to_new_email_success(self):
        resp = self.__send_success_email_change()
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.data, dict)
        self.assertEqual(resp.data["message"]["detail"], "Confirmation email was sent")

    def test_change_email_incorrect_password(self):
        data = {
            "password": self.password + "12312312",
            "new_email": self.new_email,
        }
        api_request = APIRequestFactory().post("", data=data)
        detail_view = ChangeUserEmail.as_view()
        force_authenticate(api_request, user=self.user)
        resp = detail_view(api_request, data=data)

        self.assertEqual(resp.status_code, 400)
        self.assertIsInstance(resp.data, dict)
        self.assertEqual(resp.data["message"]["detail"], "Current password is entered incorrectly")

    def test_change_email_to_current_email_address_bad_request(self):
        data = {
            "password": self.password,
            "new_email": self.user.email,
        }
        api_request = APIRequestFactory().post("", data=data)
        detail_view = ChangeUserEmail.as_view()
        force_authenticate(api_request, user=self.user)
        resp = detail_view(api_request, data=data)

        self.assertEqual(resp.status_code, 400)
        self.assertIsInstance(resp.data, dict)
        self.assertEqual(
            resp.data["message"]["detail"],
            "You already have this email address. Kindly try another one!",
        )

    def test_change_email_to_current_email_address(self):
        data = {
            "password": self.password,
            "new_email": self.new_email_2,
        }
        api_request = APIRequestFactory().post("", data=data)
        detail_view = ChangeUserEmail.as_view()
        force_authenticate(api_request, user=self.user)

        resp = detail_view(api_request, data=data)

        self.assertEqual(resp.status_code, 400)
        self.assertIsInstance(resp.data, dict)
        self.assertEqual(
            resp.data["message"]["detail"],
            "This email already exists. Kindly try another one",
        )

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
        self.assertTrue(all(key in data_keys for key in data.keys()))

    def test_confirm_code_from_email(self):
        resp = self.__send_success_email_change()

        code_obj = ConfirmCode.objects.filter(
            expiring_date__gt=timezone.now(),
            new_email__isnull=False,
            user=self.user,
        ).first()
        query = {
            "code": code_obj.code,
        }
        api_request = APIRequestFactory().get("", query)
        detail_view = ChangeUserEmail.as_view()
        force_authenticate(api_request, user=self.user)
        resp = detail_view(api_request)

        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.data, dict)

        resp_keys = ["refresh", "access", "user"]
        keys_in_resp = [key in resp.data.keys() for key in resp_keys]
        self.assertTrue(all(keys_in_resp))
        self.__check_if_data_is_full_user_info(resp.data["user"])

    def test_confirm_code_not_passed(self):
        api_request = APIRequestFactory().get("")
        detail_view = ChangeUserEmail.as_view()
        force_authenticate(api_request, user=self.user)
        resp = detail_view(api_request)

        self.assertEqual(resp.status_code, 400)
        self.assertIsInstance(resp.data, dict)
        self.assertEqual(resp.data["message"]["detail"], "provide digital code")

    def test_confirm_code_not_digit(self):
        api_request = APIRequestFactory().get("", {"code": "asd"})
        detail_view = ChangeUserEmail.as_view()
        force_authenticate(api_request, user=self.user)
        resp = detail_view(api_request)

        self.assertEqual(resp.status_code, 400)
        self.assertIsInstance(resp.data, dict)
        self.assertEqual(resp.data["message"]["detail"], "provide digital code")

    def test_confirm_code_is_invalid(self):
        api_request = APIRequestFactory().get("", {"code": "12351239834"})
        detail_view = ChangeUserEmail.as_view()
        force_authenticate(api_request, user=self.user)
        resp = detail_view(api_request)

        self.assertEqual(resp.status_code, 400)
        self.assertIsInstance(resp.data, dict)
        self.assertEqual(
            resp.data["message"]["detail"],
            "Email not confirmed. Confirmation code is expired or does not exist.",
        )
