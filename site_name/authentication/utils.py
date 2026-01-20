from django.utils.timezone import now

__all__ = ('generate_temp_email', )


def generate_temp_email():
    """Function for generating temporary email if we did not receive email from social"""
    timestamp = int(now().timestamp())
    return f"{timestamp}@temporary.com.uk"
