def site(request):
    """Values available in every template."""
    from shop.models import Brand

    return {
        "SITE_NAME": "Digicow",
        "footer_brands": Brand.objects.filter(active=True),
    }
