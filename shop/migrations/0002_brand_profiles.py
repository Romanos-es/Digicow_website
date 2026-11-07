from django.db import migrations, models


BRAND_PROFILES = {
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


def add_brand_profiles(apps, schema_editor):
    Brand = apps.get_model("shop", "Brand")
    database = schema_editor.connection.alias

    for name, profile in BRAND_PROFILES.items():
        brand, created = Brand.objects.using(database).get_or_create(
            name=name,
            defaults=profile,
        )
        if created:
            continue

        updates = {}
        if not brand.description:
            updates["description"] = profile["description"]
        if not brand.website_url:
            updates["website_url"] = profile["website_url"]
        if updates:
            Brand.objects.using(database).filter(pk=brand.pk).update(**updates)


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="brand",
            name="website_url",
            field=models.URLField(blank=True),
        ),
        migrations.RunPython(add_brand_profiles, migrations.RunPython.noop),
    ]
