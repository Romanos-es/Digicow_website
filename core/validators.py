import re

from django.core.validators import RegexValidator

# Kenyan mobile numbers: 07xx / 01xx, or +2547xx / +2541xx (the "+" is optional).
phone_validator = RegexValidator(
    r"^(?:\+?254|0)[17]\d{8}$",
    "Enter a valid Kenyan mobile number, e.g. 0712345678 or +254712345678.",
)


def normalize_phone(raw):
    """Return a phone number in +254XXXXXXXXX form when it looks Kenyan.

    Anything that does not look Kenyan is returned cleaned but otherwise
    untouched, so the validator can reject it with a clear message.
    """
    cleaned = re.sub(r"[\s\-().]", "", raw or "")
    if cleaned.startswith("+"):
        return cleaned
    if cleaned.startswith("254"):
        return "+" + cleaned
    if cleaned.startswith("0"):
        return "+254" + cleaned[1:]
    return cleaned
