from django import forms

from training.models import Attendance

from .models import ContactMessage, FarmerReview
from .validators import normalize_phone, phone_validator


class KenyanPhoneField(forms.CharField):
    """Text field that normalises and validates Kenyan mobile numbers."""

    default_validators = [phone_validator]

    def __init__(self, **kwargs):
        kwargs.setdefault("max_length", 20)
        kwargs.setdefault(
            "widget",
            forms.TextInput(attrs={"placeholder": "0712 345 678", "inputmode": "tel"}),
        )
        super().__init__(**kwargs)

    def to_python(self, value):
        value = super().to_python(value)
        return normalize_phone(value) if value else value


class StyledFormMixin:
    """Adds the site's `input` CSS class to every ordinary form widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(
                widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple, forms.RadioSelect)
            ):
                continue
            widget.attrs["class"] = (widget.attrs.get("class", "") + " input").strip()


class ContactForm(StyledFormMixin, forms.ModelForm):
    phone = KenyanPhoneField(required=False)

    class Meta:
        model = ContactMessage
        fields = ("name", "phone", "email", "message")
        widgets = {"message": forms.Textarea(attrs={"rows": 5})}


class FarmerReviewForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = FarmerReview
        fields = ("attendance", "rating", "comment")
        labels = {
            "attendance": "Training you attended",
            "rating": "Your rating",
            "comment": "Your review",
        }
        widgets = {
            "rating": forms.Select(choices=[(i, f"{i} out of 5") for i in range(1, 6)]),
            "comment": forms.Textarea(
                attrs={"rows": 5, "placeholder": "Tell us what was useful about your training."}
            ),
        }

    def __init__(self, *args, farmer, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["attendance"].queryset = (
            Attendance.objects.filter(
                farmer=farmer,
                session__status="completed",
            )
            .exclude(farmer_review__isnull=False)
            .select_related("session__topic", "session__county")
            .order_by("-session__date")
        )
        self.fields["attendance"].label_from_instance = (
            lambda attendance: (
                f"{attendance.session.topic.title} · {attendance.session.county} · "
                f"{attendance.session.date:%d %b %Y}"
            )
        )
