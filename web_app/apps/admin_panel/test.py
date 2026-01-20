from django.contrib.auth import get_user_model
from django.urls import include, path
from model_bakery import baker
from rest_framework.test import (
    APIRequestFactory,
    APITestCase,
    URLPatternsTestCase,
    force_authenticate,
)

from apps.admin_panel.views import AdminPanelUsersViewSet, ListOfRolesView


class BaseAdminViewTest(APITestCase, URLPatternsTestCase):
    urlpatterns = [path("api/admin-panel/", include("apps.admin_panel.urls"))]

    def setUp(self):
        super().setUp()
        self.admin_user = baker.make("user.User")
        self.admin_user.role = get_user_model().UserRoleChoices.ADMIN
        self.admin_user.save()


class ListOfRolesViewTest(BaseAdminViewTest):
    def test_get_roles_401(self):
        api_request = APIRequestFactory().get("")
        view = ListOfRolesView.as_view()
        resp = view(api_request)

        self.assertEqual(resp.status_code, 401)

    def test_get_all_roles_success(self):
        api_request = APIRequestFactory().get("")
        view = ListOfRolesView.as_view()
        force_authenticate(api_request, user=self.admin_user)
        resp = view(api_request)

        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.data, list)
        self.assertEqual(len(resp.data), len(get_user_model().ROLE_CHOICES))


class AdminPanelUsersViewSetTest(BaseAdminViewTest):
    def setUp(self):
        super().setUp()
        self.users = baker.make("user.User", _quantity=10)

    def test_creating_user_success(self):
        data = {
            "email": "vitalik_t+22@dataforest.ai",
            "first_name": "first_name",
            "last_name": "last_name",
            "role": 1,
            "password": "12351994",
        }
        api_request = APIRequestFactory().post("", data=data)
        view = AdminPanelUsersViewSet.as_view({"post": "create"})
        force_authenticate(api_request, user=self.admin_user)
        resp = view(api_request)

        self.assertEqual(resp.status_code, 201)
        self.assertEqual(get_user_model().objects.filter(role=1).count(), len(self.users) + 1)

    def test_updating_user_success(self):
        data = {
            "email": "vitalik_t+22@dataforest.ai",
            "first_name": "first_name",
            "last_name": "last_name",
            "role": 1,
            "password": "12351994",
        }
        api_request = APIRequestFactory().post("", data=data)
        view = AdminPanelUsersViewSet.as_view({"post": "create"})
        force_authenticate(api_request, user=self.admin_user)
        resp = view(api_request)
        new_first_name = "Hello world"
        created_user_pk = resp.data["id"]

        data = {"first_name": new_first_name, "role": 2}

        api_request = APIRequestFactory().patch("", data=data)
        view = AdminPanelUsersViewSet.as_view({"patch": "partial_update"})
        force_authenticate(api_request, user=self.admin_user)
        resp = view(api_request, id=created_user_pk)

        self.assertEqual(resp.status_code, 200)
        updated_user = get_user_model().objects.get(pk=created_user_pk)
        self.assertEqual(updated_user.first_name, new_first_name)
