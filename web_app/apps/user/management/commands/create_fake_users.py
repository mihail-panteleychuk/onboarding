from django.contrib.auth.hashers import make_password
from django.contrib.auth.management.commands import createsuperuser

from apps.user.models import User

EMAIL = "vitalik_t+{}@dataforest.ai"
PASS = "12351994"


class Command(createsuperuser.Command):
    """
    python3 manage.py create_fake_users
    """

    def handle(self, *args, **options):
        start_ind = int(input("Enter start index: "))
        acc_count = int(input("Enter accounts count: "))
        users = []

        for ind in range(start_ind, start_ind + acc_count):
            email = EMAIL.format(ind).lower()
            user = User(
                email=email,
                password=make_password(PASS),
                first_name="Fake",
                last_name=f"Test_{ind}",
                is_active=True,
                onboarding_finished=True,
            )
            print(f"FAKE user ({email}) was added.")
            users.append(user)

        User.objects.bulk_create(users)
