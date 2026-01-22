# Generated manually for billing app - data migration

from decimal import Decimal

from django.db import migrations


def create_initial_service_types(apps, schema_editor):
    """Create initial service types: Cleaning, Plumber, Electrician."""
    ServiceType = apps.get_model("billing", "ServiceType")

    # Check if service types already exist (idempotent migration)
    if ServiceType.objects.exists():
        return

    ServiceType.objects.bulk_create(
        [
            ServiceType(
                name="Cleaning",
                price_usd=Decimal("50.00"),
                is_active=True,
            ),
            ServiceType(
                name="Plumber",
                price_usd=Decimal("80.00"),
                is_active=True,
            ),
            ServiceType(
                name="Electrician",
                price_usd=Decimal("100.00"),
                is_active=True,
            ),
        ]
    )


def reverse_create_initial_service_types(apps, schema_editor):
    """Remove initial service types."""
    ServiceType = apps.get_model("billing", "ServiceType")
    ServiceType.objects.filter(
        name__in=["Cleaning", "Plumber", "Electrician"]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            create_initial_service_types,
            reverse_create_initial_service_types,
        ),
    ]
