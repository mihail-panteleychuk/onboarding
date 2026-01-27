"""Custom permissions for billing operations."""

from rest_framework.permissions import BasePermission

from apps.user.models import User


class CanAccessUserData(BasePermission):
    """
    Permission to access user data (balance, transactions).
    
    Rules:
    - Admin can access any user's data
    - User can access only their own data
    - If user_id is not provided in query params, permission is granted
      (view will handle default behavior)
    """

    def has_permission(self, request, view):
        """Check if user can access data for user_id from query params."""
        if not request.user.is_authenticated:
            return False
        
        if not hasattr(request.user, 'role'):
            return False
        
        # If user_id is not provided, allow (view will handle default behavior)
        user_id_param = request.query_params.get("user_id")
        
        if not user_id_param:
            return True
        
        # Admin can access any user's data
        if request.user.role == User.UserRoleChoices.ADMIN:
            return True
        
        # User can access only their own data
        try:
            target_user_id = str(user_id_param)
            return target_user_id == str(request.user.id)
       
        except (ValueError, TypeError):
            return False


class CanViewServiceRequest(BasePermission):
    """
    Permission to view a service request.
    
    Rules:
    - Admin can view any service request
    - User can view only their own service requests
    """

    def has_object_permission(self, request, view, obj):
        """Check if user can view this service request."""
        if not request.user.is_authenticated:
            return False
        
        if not hasattr(request.user, 'role'):
            return False
        
        # Admin can view any service request
        if request.user.role == User.UserRoleChoices.ADMIN:
            return True
        
        # User can view only their own service requests
        return obj.user_id == request.user.id


class CanCancelServiceRequest(BasePermission):
    """
    Permission to cancel a service request.
    
    Rules:
    - Admin can cancel any service request (any status)
    - User can cancel only their own requests with status 'pending'
    
    Note: Additional status check is done in BillingService.cancel_service_request
    """

    def has_object_permission(self, request, view, obj):
        """Check if user can cancel this service request."""
        if not request.user.is_authenticated:
            return False
        
        if not hasattr(request.user, 'role'):
            return False
        
        # Admin can cancel any service request
        if request.user.role == User.UserRoleChoices.ADMIN:
            return True
        
        # User can cancel only their own service requests
        # (status check will be done in service layer)
        return obj.user_id == request.user.id
