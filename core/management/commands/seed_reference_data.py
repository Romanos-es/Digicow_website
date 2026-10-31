"""Load reference counties and company brands without adding sample records."""

from django.core.management.base import BaseCommand
from django.db import transaction

from shop.models import Brand
from training.models import County

COUNTIES = [
    "Baringo", "Bomet", "Bungoma", "Busia", "Elgeyo-Marakwet", "Embu", "Garissa", "Homa Bay",
    "Isiolo", "Kajiado", "Kakamega", "Kericho", "Kiambu", "Kilifi", "Kirinyaga", "Kisii",
    "Kisumu", "Kitui", "Kwale", "Laikipia", "Lamu", "Machakos", "Makueni", "Mandera",
    "Marsabit", "Meru", "Migori", "Mombasa", "Murang'a", "Nairobi", "Nakuru", "Nandi",
    "Narok", "Nyamira", "Nyandarua", "Nyeri", "Samburu", "Siaya", "Taita-Taveta",
    "Tana River", "Tharaka-Nithi", "Trans Nzoia", "Turkana", "Uasin Gishu", "Vihiga",
    "Wajir", "West Pokot",
]

BRANDS = ["Juanco", "CKL", "Greenlife", "Asili"]


class Command(BaseCommand):
    help = "Create the county and brand reference records."

    @transaction.atomic
    def handle(self, *args, **options):
        for name in COUNTIES:
            County.objects.get_or_create(name=name)
        for name in BRANDS:
            Brand.objects.get_or_create(name=name, defaults={"slug": name.lower()})
        self.stdout.write(
            self.style.SUCCESS(f"{len(COUNTIES)} counties and {len(BRANDS)} brands ready.")
        )
