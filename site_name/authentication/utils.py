from django.utils.timezone import now


def generate_temp_email():
    """Function for generating temporary email if we did not receive email from social"""
    timestamp = int(now().timestamp())
    return f"{timestamp}@temporary.com.uk"
