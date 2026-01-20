import os
from getpass import getpass

from django.contrib.auth.hashers import make_password
from django.contrib.auth.management.commands import createsuperuser

from user.models import User

"""
python3 manage.py add_admin_user
"""


class Command(createsuperuser.Command):

    def handle(self, *args, **options):
        email = input('Enter user email: ')
        password = getpass('Enter user password: ')

        if not password or not email:
            raise Exception('Email or password are not provided.')

        user = User.objects.filter(email=email.lower()).first()
        if user:
            return f"Admin already exists with email {user.email}."

        User.objects.create(
            email=email.lower(),
            password=make_password(password),
            first_name='ADMIN',
            last_name='ADMIN',
            is_staff=True,
            is_superuser=True,
            is_active=True
        )

        return f'Admin({email}) was added.'
