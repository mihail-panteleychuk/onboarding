"""Tests for billing app."""

import unittest.mock
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import include, path, reverse
from model_bakery import baker
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase, URLPatternsTestCase, force_authenticate

from apps.billing.constants import ServiceStatus, TransactionDirection, TransactionKind
from apps.billing.models import BalanceTransaction, ServiceRequest, ServiceType
from apps.billing.services import BillingService

User = get_user_model()


# Models


class ServiceTypeModelTest(TestCase):
    """Tests for the ServiceType model"""

    def setUp(self):
        """Preparing data before each test"""
        # Use an existing ServiceType from the migration or create a new one with a unique name
        self.service_type, _ = ServiceType.objects.get_or_create(
            name="Test Service Type",
            defaults={
                "price_usd": Decimal("50.00"),
                "is_active": True,
            },
        )

    
    def test_str(self):
        """Test: String representation of a model"""
        expected = f"{self.service_type.name} (50.00 USD)"
        self.assertEqual(str(self.service_type), expected)

    
    def test_is_active_filter(self):
        """Test: Filtering Active Services"""
        # Create an inactive service with a unique name
        inactive_service, _ = ServiceType.objects.get_or_create(
            name="Inactive Test Service",
            defaults={
                "price_usd": Decimal("30.00"),
                "is_active": False,
            },
        )
        
        active_services = ServiceType.objects.filter(is_active=True)
        self.assertIn(self.service_type, active_services)
        self.assertNotIn(inactive_service, active_services)


class BalanceTransactionModelTest(TestCase):
    """Tests for the BalanceTransaction model"""

    def setUp(self):
        self.user = baker.make("user.User")

    
    def test_calculate_balance_simple(self):
        """Test: Balance calculation with one transaction"""        
        baker.make(
            "billing.BalanceTransaction",
            user=self.user,
            direction=TransactionDirection.IN,
            kind=TransactionKind.TOPUP,
            amount=Decimal("100.00"),
        )
       
        balance = BalanceTransaction.objects.calculate_user_balance(self.user)
        self.assertEqual(balance, Decimal("100.00"))

    
    def test_calculate_balance_multiple_transactions(self):
        """Test: Balance calculation with multiple transactions"""        
        baker.make(
            "billing.BalanceTransaction",
            user=self.user,
            direction=TransactionDirection.IN,
            kind=TransactionKind.TOPUP,
            amount=Decimal("100.00"),
        )

        # Reservation
        baker.make(
            "billing.BalanceTransaction",
            user=self.user,
            direction=TransactionDirection.OUT,
            kind=TransactionKind.RESERVE,
            amount=Decimal("30.00"),
        )

        # Another addition
        baker.make(
            "billing.BalanceTransaction",
            user=self.user,
            direction=TransactionDirection.IN,
            kind=TransactionKind.TOPUP,
            amount=Decimal("50.00"),
        )

        # Check the balance: 100 - 30 + 50 = 120
        balance = BalanceTransaction.objects.calculate_user_balance(self.user)
        self.assertEqual(balance, Decimal("120.00"))

    
    def test_calculate_balance_excludes_capture(self):
        """Test: CAPTURE is not included in the balance sheet (already included in RESERVE)"""        
        baker.make(
            "billing.BalanceTransaction",
            user=self.user,
            direction=TransactionDirection.OUT,
            kind=TransactionKind.RESERVE,
            amount=Decimal("50.00"),
        )

        # CAPTURE should not affect balance (history only)
        baker.make(
            "billing.BalanceTransaction",
            user=self.user,
            direction=TransactionDirection.OUT,
            kind=TransactionKind.CAPTURE,
            amount=Decimal("50.00"),
        )

        # The balance should be -50 (only RESERVE), not -100
        balance = BalanceTransaction.objects.calculate_user_balance(self.user)
        self.assertEqual(balance, Decimal("-50.00"))

    
    def test_signed_amount_in(self):
        """Test: signed_amount for IN transaction (positive)"""
        transaction = baker.make(
            "billing.BalanceTransaction",
            user=self.user,
            direction=TransactionDirection.IN,
            kind=TransactionKind.TOPUP,
            amount=Decimal("100.00"),
        )

        self.assertEqual(transaction.signed_amount, Decimal("100.00"))

    
    def test_signed_amount_out(self):
        """Test: signed_amount for OUT transaction (negative)"""
        transaction = baker.make(
            "billing.BalanceTransaction",
            user=self.user,
            direction=TransactionDirection.OUT,
            kind=TransactionKind.RESERVE,
            amount=Decimal("50.00"),
        )

        self.assertEqual(transaction.signed_amount, Decimal("-50.00"))


class ServiceRequestModelTest(TestCase):
    """Tests for the ServiceRequest model"""

    def setUp(self):
        self.user = baker.make("user.User")
        # Use an existing ServiceType from the migration or create a new one with a unique name
        self.service_type, _ = ServiceType.objects.get_or_create(
            name="Test Cleaning Service",
            defaults={
                "price_usd": Decimal("50.00"),
                "is_active": True,
            },
        )
        self.request = baker.make(
            "billing.ServiceRequest",
            user=self.user,
            service_type=self.service_type,
            status=ServiceStatus.PENDING,
        )

    
    def test_reserve_funds(self):
        """Test: Is the funds reservation working correctly"""
        # We check that there are no reserved funds initially
        self.assertEqual(self.request.reserved_amount, Decimal("0.00"))

        # We reserve funds
        transaction = self.request.reserve_funds()

        # Checking the result
        self.assertEqual(transaction.kind, TransactionKind.RESERVE)
        self.assertEqual(transaction.direction, TransactionDirection.OUT)
        self.assertEqual(transaction.amount, Decimal("50.00"))
        self.assertEqual(self.request.reserved_amount, Decimal("50.00"))
        self.assertEqual(transaction.user, self.user)
        self.assertEqual(transaction.service_request, self.request)

    
    def test_reserve_funds_already_reserved(self):
        """Test: You can't reserve twice"""
        # We are reserving for the first time
        self.request.reserve_funds()

        # We're trying to reserve a second time - there must be an error.
        with self.assertRaises(ValueError) as context:
            self.request.reserve_funds()

        self.assertIn("already reserved", str(context.exception))

    
    def test_reserve_funds_not_pending(self):
        """Test: Cannot reserve for non-pending request"""
        # Change the status to confirmed
        self.request.status = ServiceStatus.CONFIRMED
        self.request.save()

        # We're trying to make a reservation - there must be an error.
        with self.assertRaises(ValueError) as context:
            self.request.reserve_funds()

        self.assertIn("status", str(context.exception).lower())

    
    def test_refund_reserved_funds(self):
        """Test: Refund of Reserved Funds"""
        # First we reserve
        self.request.reserve_funds()
        self.assertEqual(self.request.reserved_amount, Decimal("50.00"))

        # We return funds
        transaction = self.request.refund_reserved_funds()

        # Checking the result
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.kind, TransactionKind.REFUND)
        self.assertEqual(transaction.direction, TransactionDirection.IN)
        self.assertEqual(transaction.amount, Decimal("50.00"))
        self.assertEqual(self.request.reserved_amount, Decimal("0.00"))

    
    def test_refund_no_funds(self):
        """Test: Refund when there are no reserved funds"""
        # We're not reserving funds (reserved_amount = 0)
        # # We're attempting to return the funds - None should be returned.
        transaction = self.request.refund_reserved_funds()
        self.assertIsNone(transaction)

    
    def test_cancel(self):
        """Test: Cancel an application"""
        # We reserve funds
        self.request.reserve_funds()

        # We cancel the application
        transaction = self.request.cancel()

        # Checking the result
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, ServiceStatus.CANCELLED)
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.kind, TransactionKind.REFUND)

    
    def test_cancel_already_cancelled(self):
        """Test: Cancelling an already cancelled application"""
        # Canceling for the first time
        self.request.cancel()

        # We try to cancel a second time - it should return None
        transaction = self.request.cancel()
        self.assertIsNone(transaction)

    
    def test_can_be_cancelled_by_user(self):
        """Test: Checking the User Cancelability"""
        # Pending application may be cancelled
        self.request.status = ServiceStatus.PENDING
        self.assertTrue(self.request.can_be_cancelled_by_user())

        # A confirmed request cannot be cancelled by the user.
        self.request.status = ServiceStatus.CONFIRMED
        self.assertFalse(self.request.can_be_cancelled_by_user())


# Services

class BillingServiceTest(TestCase):
    """Tests for BillingService"""

    def setUp(self):
        self.user = baker.make("user.User")
        # Use an existing ServiceType from the migration or create a new one with a unique name
        self.service_type, _ = ServiceType.objects.get_or_create(
            name="Test Service for BillingService",
            defaults={
                "price_usd": Decimal("50.00"),
                "is_active": True,
            },
        )

    
    def test_get_user_balance(self):
        """Test: Getting a User's Balance"""
        # Creating transactions
        baker.make(
            "billing.BalanceTransaction",
            user=self.user,
            direction=TransactionDirection.IN,
            kind=TransactionKind.TOPUP,
            amount=Decimal("100.00"),
        )

        balance = BillingService.get_user_balance(self.user)
        self.assertEqual(balance, Decimal("100.00"))

    
    def test_check_sufficient_balance(self):
        """Test: Checking the sufficiency of the balance"""
        # Top up your balance
        BillingService.create_topup_transaction(self.user, Decimal("100.00"))

        # We check the sufficiency for the amount of 50
        self.assertTrue(BillingService.check_sufficient_balance(self.user, Decimal("50.00")))

        # We check the sufficiency for the sum of 100
        self.assertTrue(BillingService.check_sufficient_balance(self.user, Decimal("100.00")))

        # We check the sufficiency for the amount of 150 (not enough)
        self.assertFalse(BillingService.check_sufficient_balance(self.user, Decimal("150.00")))

    
    def test_create_service_request_success(self):
        """Test: Successful application creation"""
        # Top up your balance
        BillingService.create_topup_transaction(self.user, Decimal("100.00"))

        # Create an application
        request = BillingService.create_service_request(
            user=self.user,
            service_type=self.service_type,
        )

        # Checking the result
        self.assertEqual(request.status, ServiceStatus.PENDING)
        self.assertEqual(request.user, self.user)
        self.assertEqual(request.service_type, self.service_type)
        self.assertEqual(request.reserved_amount, Decimal("50.00"))

        # We check that the balance has decreased
        balance = BillingService.get_user_balance(self.user)
        self.assertEqual(balance, Decimal("50.00"))  # 100 - 50 = 50

    
    def test_create_service_request_insufficient_balance(self):
        """Test: Insufficient balance error"""
        # We are NOT topping up our balance (balance = 0)
        # # We are trying to create a request - there should be an error
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError) as context:
            BillingService.create_service_request(
                user=self.user,
                service_type=self.service_type,
            )

        # Checking the error text
        error = context.exception.detail
        self.assertIn("balance", error)
        self.assertIn("Insufficient balance", str(error["balance"]))

    
    def test_create_service_request_inactive_service(self):
        """Test: Error when service is inactive"""
        # Making the service inactive
        self.service_type.is_active = False
        self.service_type.save()

        # Top up your balance
        BillingService.create_topup_transaction(self.user, Decimal("100.00"))

        # We're trying to create a request - there must be an error.
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError) as context:
            BillingService.create_service_request(
                user=self.user,
                service_type=self.service_type,
            )

        error = context.exception.detail
        self.assertIn("service_type", error)

    
    def test_create_topup_transaction(self):
        """Test: Creating a Deposit Transaction"""
        transaction = BillingService.create_topup_transaction(
            user=self.user,
            amount=Decimal("100.00"),
            external_id="stripe_session_123",
        )

        # Checking the result
        self.assertEqual(transaction.kind, TransactionKind.TOPUP)
        self.assertEqual(transaction.direction, TransactionDirection.IN)
        self.assertEqual(transaction.amount, Decimal("100.00"))
        self.assertEqual(transaction.external_id, "stripe_session_123")

        # Checking the balance
        balance = BillingService.get_user_balance(self.user)
        self.assertEqual(balance, Decimal("100.00"))

    
    def test_create_topup_transaction_idempotency(self):
        """Test: Idempotency (does not create duplicates)"""
        # Create a transaction with external_id
        transaction1 = BillingService.create_topup_transaction(
            user=self.user,
            amount=Decimal("100.00"),
            external_id="stripe_session_123",
        )

        # We are trying to create it again with the same external_id
        transaction2 = BillingService.create_topup_transaction(
            user=self.user,
            amount=Decimal("100.00"),
            external_id="stripe_session_123",
        )

        # The same transaction should return
        self.assertEqual(transaction1.id, transaction2.id)

        # The balance should not double
        balance = BillingService.get_user_balance(self.user)
        self.assertEqual(balance, Decimal("100.00"))


# API endpoints


class BaseBillingAPITest(APITestCase, URLPatternsTestCase):
    """Base class for the billing module's API tests"""

    urlpatterns = [path("api/billing/", include("apps.billing.urls"))]

    def setUp(self):
        super().setUp()
        # Creating users
        self.user = baker.make("user.User")
        self.other_user = baker.make("user.User")
        self.admin = baker.make("user.User", role=User.UserRoleChoices.ADMIN)

        # Create a service type (use an existing one or create a new one with a unique name)
        self.service_type, _ = ServiceType.objects.get_or_create(
            name="Test Service for API",
            defaults={
                "price_usd": Decimal("50.00"),
                "is_active": True,
            },
        )


class ServiceTypeViewSetTest(BaseBillingAPITest):
    """Tests for ServiceTypeViewSet"""

    def test_list_service_types_401(self):
        """Test: Unauthorized error"""
        url = reverse("service-type-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 401)


    def test_list_service_types_success(self):
        """Test: Successful List of Services"""
        self.client.force_authenticate(user=self.user)
        url = reverse("service-type-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # ServiceTypeViewSet might return paginated response
        services = response.data if isinstance(response.data, list) else response.data.get("results", [])
        self.assertIsInstance(services, list)
        self.assertGreater(len(services), 0)


    def test_list_only_active(self):
        """Test: only active services in the list"""
        # Create an inactive service with a unique name
        ServiceType.objects.get_or_create(
            name="Inactive Service for Test",
            defaults={
                "price_usd": Decimal("30.00"),
                "is_active": False,
            },
        )

        self.client.force_authenticate(user=self.user)
        url = reverse("service-type-list")
        response = self.client.get(url)

        # We check that all services are active
        # Handle pagination if present
        services = response.data if isinstance(response.data, list) else response.data.get("results", [])
        for service in services:
            self.assertTrue(service["is_active"])



class BalanceViewTest(BaseBillingAPITest):
    """Tests for BalanceView"""

    def setUp(self):
        super().setUp()
        # Top up the user's balance
        BillingService.create_topup_transaction(self.user, Decimal("100.00"))

    
    def test_get_balance_401(self):
        """Test: Unauthorized error"""
        url = reverse("balance")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 401)


    def test_get_balance_user_own(self):
        """Test: The user sees their balance"""
        self.client.force_authenticate(user=self.user)
        url = reverse("balance")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["balance"], "100.00")
        self.assertIn("transactions", response.data)

    
    def test_get_balance_user_other_user_403(self):
        """Test: User cannot see someone else's balance"""
        self.client.force_authenticate(user=self.user)
        url = reverse("balance")
        response = self.client.get(url, {"user_id": str(self.other_user.id)})

        self.assertEqual(response.status_code, 403)

    
    def test_get_balance_admin_list(self):
        """Test: Admin sees a list of all users"""
        self.client.force_authenticate(user=self.admin)
        url = reverse("balance")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.data)
        self.assertIn("count", response.data)

    
    def test_get_balance_admin_specific_user(self):
        """Test: Admin can see a specific user's balance"""
        self.client.force_authenticate(user=self.admin)
        url = reverse("balance")
        response = self.client.get(url, {"user_id": str(self.user.id)})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["balance"], "100.00")


class ServiceRequestViewSetTest(BaseBillingAPITest):
    """Tests for ServiceRequestViewSet"""

    def setUp(self):
        super().setUp()
        # Top up the user's balance
        BillingService.create_topup_transaction(self.user, Decimal("100.00"))

    
    def test_create_request_success(self):
        """Test: Successful creation of a request via API"""
        self.client.force_authenticate(user=self.user)
        url = reverse("service-request-list")
        response = self.client.post(
            url,
            {"service_type_id": str(self.service_type.id)},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "pending")
        self.assertEqual(response.data["service_type"]["id"], str(self.service_type.id))

    
    def test_create_request_insufficient_balance(self):
        """Test: Insufficient balance error"""
        # Create a user WITHOUT a balance
        poor_user = baker.make("user.User")
        self.client.force_authenticate(user=poor_user)

        url = reverse("service-request-list")
        response = self.client.post(
            url,
            {"service_type_id": str(self.service_type.id)},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("balance", str(response.data["detail"]))

    
    def test_list_requests_user_own(self):
        """Test: The user sees only their own requests"""
        # We create requests for different users
        request1 = baker.make("billing.ServiceRequest", user=self.user)
        request2 = baker.make("billing.ServiceRequest", user=self.other_user)

        self.client.force_authenticate(user=self.user)
        url = reverse("service-request-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # We check that only our application is visible
        # Handle pagination - response.data is a dict with "results" key
        results = response.data if isinstance(response.data, list) else response.data.get("results", [])
        request_ids = [r["id"] for r in results]
        self.assertIn(str(request1.id), request_ids)
        self.assertNotIn(str(request2.id), request_ids)

    
    def test_list_requests_admin_all(self):
        """Test: Admin sees all requests"""
        # We create requests for different users
        request1 = baker.make("billing.ServiceRequest", user=self.user)
        request2 = baker.make("billing.ServiceRequest", user=self.other_user)

        self.client.force_authenticate(user=self.admin)
        url = reverse("service-request-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # We check that all applications are visible
        # Handle pagination - response.data is a dict with "results" key
        results = response.data if isinstance(response.data, list) else response.data.get("results", [])
        request_ids = [r["id"] for r in results]
        self.assertIn(str(request1.id), request_ids)
        self.assertIn(str(request2.id), request_ids)

    
    def test_retrieve_request_success(self):
        """Test: Successfully receiving detailed information about the application"""
        request = baker.make("billing.ServiceRequest", user=self.user)
        
        self.client.force_authenticate(user=self.user)
        url = reverse("service-request-detail", kwargs={"pk": str(request.id)})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], str(request.id))
        # response.data["user"] can be UUID object or string, convert to string for comparison
        self.assertEqual(str(response.data["user"]), str(self.user.id))

    
    def test_retrieve_request_user_other_403(self):
        """Test: User cannot see someone else's request"""
        request = baker.make("billing.ServiceRequest", user=self.other_user)
        
        self.client.force_authenticate(user=self.user)
        url = reverse("service-request-detail", kwargs={"pk": str(request.id)})
        response = self.client.get(url)
        
        # DRF returns 404 when object is not in queryset (filtered by get_queryset)
        # This is expected behavior - user cannot see other user's requests
        self.assertEqual(response.status_code, 404)

    
    def test_cancel_request_user_own_pending(self):
        """Test: User can cancel their pending request"""
        request = baker.make(
            "billing.ServiceRequest",
            user=self.user,
            status=ServiceStatus.PENDING,
        )
        request.reserve_funds()
        initial_balance = BillingService.get_user_balance(self.user)
        
        self.client.force_authenticate(user=self.user)
        # Use direct URL path instead of reverse to avoid URL name issues
        url = f"/api/billing/requests/{request.id}/cancel/"
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 200)
        request.refresh_from_db()
        self.assertEqual(request.status, ServiceStatus.CANCELLED)
        # Check that funds were refunded
        new_balance = BillingService.get_user_balance(self.user)
        self.assertGreater(new_balance, initial_balance)

    
    def test_cancel_request_user_not_owner_403(self):
        """Test: A user cannot cancel someone else's request"""
        request = baker.make("billing.ServiceRequest", user=self.other_user)
        
        self.client.force_authenticate(user=self.user)
        # Use direct URL path instead of reverse to avoid URL name issues
        url = f"/api/billing/requests/{request.id}/cancel/"
        response = self.client.post(url)
        
        # DRF returns 404 when object is not in queryset (filtered by get_queryset)
        self.assertIn(response.status_code, [403, 404])

    
    def test_cancel_request_user_not_pending_400(self):
        """Test: User cannot cancel a non-pending request"""
        request = baker.make(
            "billing.ServiceRequest",
            user=self.user,
            status=ServiceStatus.CONFIRMED,
        )
        
        self.client.force_authenticate(user=self.user)
        # Use direct URL path
        url = f"/api/billing/requests/{request.id}/cancel/"
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 400)

    
    def test_cancel_request_admin_any(self):
        """Test: Admin can cancel any request"""
        # Create request with PENDING status and reserve funds
        request = baker.make(
            "billing.ServiceRequest",
            user=self.user,
            status=ServiceStatus.PENDING,
        )
        request.reserve_funds()
        # Change status to CONFIRMED (simulating admin workflow)
        request.status = ServiceStatus.CONFIRMED
        request.save()
        
        self.client.force_authenticate(user=self.admin)
        # Use direct URL path
        url = f"/api/billing/requests/{request.id}/cancel/"
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 200)
        request.refresh_from_db()
        self.assertEqual(request.status, ServiceStatus.CANCELLED)

    
    def test_change_status_admin_only(self):
        """Test: Status change is only available to the admin"""
        request = baker.make(
            "billing.ServiceRequest",
            user=self.user,
            status=ServiceStatus.PENDING,
        )
        request.reserve_funds()
        
        self.client.force_authenticate(user=self.user)
        # Use direct URL path
        url = f"/api/billing/requests/{request.id}/change-status/"
        response = self.client.post(url, {"status": ServiceStatus.CONFIRMED}, format="json")
        
        self.assertEqual(response.status_code, 403)

    
    def test_change_status_admin_success(self):
        """Test: Admin can change the status of an application"""
        request = baker.make(
            "billing.ServiceRequest",
            user=self.user,
            status=ServiceStatus.PENDING,
        )
        request.reserve_funds()
        
        self.client.force_authenticate(user=self.admin)
        # Use direct URL path
        url = f"/api/billing/requests/{request.id}/change-status/"
        response = self.client.post(url, {"status": ServiceStatus.CONFIRMED}, format="json")
        
        self.assertEqual(response.status_code, 200)
        request.refresh_from_db()
        self.assertEqual(request.status, ServiceStatus.CONFIRMED)

    
    def test_change_status_invalid_transition(self):
        """Test: Error during invalid status transition"""
        request = baker.make(
            "billing.ServiceRequest",
            user=self.user,
            status=ServiceStatus.COMPLETED,
        )
        
        self.client.force_authenticate(user=self.admin)
        # Use direct URL path
        url = f"/api/billing/requests/{request.id}/change-status/"
        response = self.client.post(url, {"status": ServiceStatus.PENDING}, format="json")
        
        self.assertEqual(response.status_code, 400)

    
    def test_list_search(self):
        """Test: Full-text search works"""
        # Create request with specific user email
        user_with_email = baker.make("user.User", email="testsearch@example.com")
        request = baker.make("billing.ServiceRequest", user=user_with_email)
        
        self.client.force_authenticate(user=self.admin)
        url = reverse("service-request-list")
        response = self.client.get(url, {"search": "testsearch"})
        
        self.assertEqual(response.status_code, 200)
        # Handle pagination
        results = response.data if isinstance(response.data, list) else response.data.get("results", [])
        request_ids = [r["id"] for r in results]
        self.assertIn(str(request.id), request_ids)

    
    def test_list_filter_by_status(self):
        """Test: Filtering by status works"""
        pending_request = baker.make(
            "billing.ServiceRequest",
            user=self.user,
            status=ServiceStatus.PENDING,
        )
        confirmed_request = baker.make(
            "billing.ServiceRequest",
            user=self.user,
            status=ServiceStatus.CONFIRMED,
        )
        
        self.client.force_authenticate(user=self.user)
        url = reverse("service-request-list")
        response = self.client.get(url, {"status": ServiceStatus.PENDING})
        
        self.assertEqual(response.status_code, 200)
        # Handle pagination
        results = response.data if isinstance(response.data, list) else response.data.get("results", [])
        request_ids = [r["id"] for r in results]
        self.assertIn(str(pending_request.id), request_ids)
        self.assertNotIn(str(confirmed_request.id), request_ids)


class BalanceTransactionsViewTest(BaseBillingAPITest):
    """Tests for BalanceTransactionsView"""

    def setUp(self):
        super().setUp()
        # Create transactions for user
        baker.make(
            "billing.BalanceTransaction",
            user=self.user,
            direction=TransactionDirection.IN,
            kind=TransactionKind.TOPUP,
            amount=Decimal("100.00"),
        )
        baker.make(
            "billing.BalanceTransaction",
            user=self.user,
            direction=TransactionDirection.OUT,
            kind=TransactionKind.RESERVE,
            amount=Decimal("30.00"),
        )

    
    def test_get_transactions_401(self):
        """Test: Unauthorized error"""
        url = reverse("balance-transactions")
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 401)

    
    def test_get_transactions_user_own(self):
        """Test: The user can see their transaction"""
        self.client.force_authenticate(user=self.user)
        url = reverse("balance-transactions")
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.data)
        self.assertIn("count", response.data)
        self.assertGreater(len(response.data["results"]), 0)

    
    def test_get_transactions_user_other_403(self):
        """Test: User cannot see other people's transactions"""
        self.client.force_authenticate(user=self.user)
        url = reverse("balance-transactions")
        response = self.client.get(url, {"user_id": str(self.other_user.id)})
        
        self.assertEqual(response.status_code, 403)

    
    def test_get_transactions_admin(self):
        """Test: Admin can see any user's transactions"""
        self.client.force_authenticate(user=self.admin)
        url = reverse("balance-transactions")
        response = self.client.get(url, {"user_id": str(self.user.id)})
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.data)
        self.assertGreater(len(response.data["results"]), 0)

    
    def test_get_transactions_pagination(self):
        """Test: Pagination works"""
        # Create more transactions
        for _ in range(25):
            baker.make(
                "billing.BalanceTransaction",
                user=self.user,
                direction=TransactionDirection.IN,
                kind=TransactionKind.TOPUP,
                amount=Decimal("10.00"),
            )
        
        self.client.force_authenticate(user=self.user)
        url = reverse("balance-transactions")
        response = self.client.get(url, {"page_size": 10})
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 10)
        self.assertIn("next", response.data)


class BalanceTopUpViewTest(BaseBillingAPITest):
    """Tests for BalanceTopUpView"""

    def test_topup_401(self):
        """Test: Unauthorized error"""
        url = reverse("balance-topup")
        response = self.client.post(url, {"amount": "10.00"}, format="json")
        
        self.assertEqual(response.status_code, 401)

    
    def test_topup_success(self):
        """Test: Successfully Created a Checkout Session"""
        self.client.force_authenticate(user=self.user)
        url = reverse("balance-topup")
        
        # Mock Stripe to avoid actual API calls in tests
        with unittest.mock.patch(
            "apps.billing.stripe_service.StripeService.create_checkout_session_for_topup"
        ) as mock_create:
            mock_create.return_value = {
                "url": "https://checkout.stripe.com/test",
                "session_id": "cs_test_123",
            }
            
            response = self.client.post(url, {"amount": "10.00"}, format="json")
            
            self.assertEqual(response.status_code, 200)
            self.assertIn("checkout_url", response.data)
            self.assertIn("session_id", response.data)
            mock_create.assert_called_once()

    
    def test_topup_invalid_amount(self):
        """Test: Invalid Amount Error"""
        self.client.force_authenticate(user=self.user)
        url = reverse("balance-topup")
        response = self.client.post(url, {"amount": "-10.00"}, format="json")
        
        self.assertEqual(response.status_code, 400)

    
    def test_topup_amount_too_large(self):
        """Test: Error when the amount is greater than $10,000"""
        self.client.force_authenticate(user=self.user)
        url = reverse("balance-topup")
        response = self.client.post(url, {"amount": "10001.00"}, format="json")
        
        self.assertEqual(response.status_code, 400)


# Additional service tests

class BillingServiceAdditionalTest(TestCase):
    """Additional tests for BillingService"""

    def setUp(self):
        self.user = baker.make("user.User")
        self.service_type, _ = ServiceType.objects.get_or_create(
            name="Test Service Additional",
            defaults={
                "price_usd": Decimal("50.00"),
                "is_active": True,
            },
        )

    
    def test_cancel_service_request_by_user(self):
        """Test: User cancellation of an application"""
        # Top up balance and create request
        BillingService.create_topup_transaction(self.user, Decimal("100.00"))
        request = BillingService.create_service_request(
            user=self.user,
            service_type=self.service_type,
        )
        initial_balance = BillingService.get_user_balance(self.user)
        
        # Cancel request
        transaction = BillingService.cancel_service_request_by_user(
            user=self.user,
            service_request=request,
        )
        
        # Check results
        request.refresh_from_db()
        self.assertEqual(request.status, ServiceStatus.CANCELLED)
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.kind, TransactionKind.REFUND)
        # Check balance was refunded
        new_balance = BillingService.get_user_balance(self.user)
        self.assertGreater(new_balance, initial_balance)

    
    def test_cancel_service_request_by_user_not_owner(self):
        """Test: Error when canceling someone else's request"""
        other_user = baker.make("user.User")
        BillingService.create_topup_transaction(other_user, Decimal("100.00"))
        request = BillingService.create_service_request(
            user=other_user,
            service_type=self.service_type,
        )
        
        with self.assertRaises(ValidationError):
            BillingService.cancel_service_request_by_user(
                user=self.user,
                service_request=request,
            )

    
    def test_change_service_request_status(self):
        """Test: Changing the application status by the administrator"""
        BillingService.create_topup_transaction(self.user, Decimal("100.00"))
        request = BillingService.create_service_request(
            user=self.user,
            service_type=self.service_type,
        )
        
        # Change status to confirmed
        updated_request = BillingService.change_service_request_status(
            service_request=request,
            new_status=ServiceStatus.CONFIRMED.value,
        )
        
        self.assertEqual(updated_request.status, ServiceStatus.CONFIRMED)
        # Check that CAPTURE transaction was created
        capture_transactions = BalanceTransaction.objects.filter(
            user=self.user,
            kind=TransactionKind.CAPTURE,
            service_request=request,
        )
        self.assertEqual(capture_transactions.count(), 1)

    
    def test_change_status_to_cancelled_refunds(self):
        """Test: Changing the status to canceled returns funds"""
        BillingService.create_topup_transaction(self.user, Decimal("100.00"))
        request = BillingService.create_service_request(
            user=self.user,
            service_type=self.service_type,
        )
        initial_balance = BillingService.get_user_balance(self.user)
        
        # Change status to cancelled
        BillingService.change_service_request_status(
            service_request=request,
            new_status=ServiceStatus.CANCELLED.value,
        )
        
        # Refresh request from DB to get updated status and reserved_amount
        request.refresh_from_db()
        
        # Verify that reserved_amount was reset
        self.assertEqual(request.reserved_amount, Decimal("0.00"))
        self.assertEqual(request.status, ServiceStatus.CANCELLED)
        
        # Check that REFUND transaction was created
        refund_transactions = BalanceTransaction.objects.filter(
            user=self.user,
            kind=TransactionKind.REFUND,
            service_request=request,
        )
        self.assertEqual(refund_transactions.count(), 1)
        
        # Check balance was refunded
        new_balance = BillingService.get_user_balance(self.user)
        self.assertGreater(new_balance, initial_balance)
