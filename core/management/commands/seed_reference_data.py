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

BRANDS = {
    "Juanco": {
        "slug": "juanco",
        "description": (
            "Juanco SPS offers agricultural inputs and pest-control products, alongside "
            "technical services for farmers and support for farming projects. Its published "
            "crop sectors include coffee, floriculture, cereals, fruit trees, horticulture, "
            "herbs and tea."
        ),
        "website_url": "https://juancogroup.co.ke/juancosps/about-us/",
    },
    "CKL": {
        "slug": "ckl",
        "description": (
            "CKL Africa supplies livestock and crop-farming solutions, including "
            "crop-protection products. The company says it has served the agricultural "
            "sector since 1906."
        ),
        "website_url": "https://www.ckl.africa/",
    },
    "Greenlife": {
        "slug": "greenlife",
        "description": (
            "Greenlife Crop Protection Africa lists crop-protection and crop-nutrition "
            "products, seeds and farm equipment, and describes agronomy support including "
            "on-farm training and soil assessment."
        ),
        "website_url": "https://www.greenlife.co.ke/",
    },
    "Asili": {
        "slug": "asili",
        "description": (
            "Kenya Climate Ventures identifies Asili Granulated Fertilizer as a product "
            "made by Kenyan producer Agriflora Solutions from decomposed animal and "
            "plant waste. Confirm current product details and availability before ordering."
        ),
        "website_url": (
            "https://kcv.co.ke/kcv-invests-in-agriflora-solutions-for-impact-in-sustainable-food-and-agriculture/"
        ),
    },
}


class Command(BaseCommand):
    help = "Create the county and brand reference records."

    @transaction.atomic
    def handle(self, *args, **options):
        for name in COUNTIES:
            County.objects.get_or_create(name=name)
        for name, defaults in BRANDS.items():
            Brand.objects.get_or_create(name=name, defaults=defaults)
        self.stdout.write(
            self.style.SUCCESS(f"{len(COUNTIES)} counties and {len(BRANDS)} brands ready.")
        )
