from django.utils import timezone


def generate_temp_email() -> str:
    """
    Generates a temporary email address if an email is not received from a social platform.

    Returns:
        str: A temporary email address in the format 'timestamp@temporary.com.uk'.
    """
    timestamp = int(timezone.now().timestamp())
    return f"{timestamp}@temporary.com.uk"
