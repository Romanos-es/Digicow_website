import re

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from accounts.models import User
from core.forms import KenyanPhoneField, StyledFormMixin
from core.validators import normalize_phone, phone_validator

from .models import Attendance, Farmer, Topic, TrainingSession


class TopicForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Topic
        fields = ("title", "summary", "active")
        widgets = {"summary": forms.Textarea(attrs={"rows": 4})}


class TrainingSessionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = TrainingSession
        fields = ("topic", "county", "trainer", "venue", "date", "start_time", "status", "notes")
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "start_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        topic_filter = Q(active=True)
        if self.instance.pk and self.instance.topic_id:
            topic_filter |= Q(pk=self.instance.topic_id)
        self.fields["topic"].queryset = Topic.objects.filter(topic_filter)
        self.fields["trainer"].queryset = User.objects.filter(
            role=User.Role.TRAINER, is_active=True
        ).order_by("first_name", "username")
        self.fields["trainer"].label_from_instance = lambda user: user.display_name
        self.fields["trainer"].required = True


class FarmerForm(StyledFormMixin, forms.ModelForm):
    phone = KenyanPhoneField()

    class Meta:
        model = Farmer
        fields = ("full_name", "phone", "county", "location", "farm_focus")


class AttendanceRegistrationForm(forms.Form):
    """Trainer registers who attended: tick known farmers and/or paste new ones."""

    farmers = forms.ModelMultipleChoiceField(
        queryset=Farmer.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Farmers already on the system",
    )
    new_farmers = forms.CharField(
        required=False,
        label="New farmers",
        help_text="One per line: Full name, phone number (e.g. Jane Wanjiku, 0712345678).",
        widget=forms.Textarea(attrs={"rows": 6, "class": "input"}),
    )
    group_photo = forms.ImageField(
        required=False,
        label="Training group photo",
        help_text="Upload a clear photo of the training group.",
    )

    def __init__(self, *args, session, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = session
        self.parsed_new = []
        self.fields["farmers"].queryset = (
            Farmer.objects.filter(county=session.county)
            .exclude(attendances__session=session)
            .order_by("full_name")
        )

    def clean_new_farmers(self):
        raw = self.cleaned_data.get("new_farmers", "")
        parsed, errors, seen = [], [], set()
        for number, line in enumerate(raw.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            parts = [part.strip() for part in re.split(r"[,;\t]", line)]
            if len(parts) < 2 or not parts[0] or not parts[1]:
                errors.append(f"Line {number}: use 'Full name, phone number'.")
                continue
            phone = normalize_phone(parts[1])
            try:
                phone_validator(phone)
            except ValidationError:
                errors.append(f"Line {number}: '{parts[1]}' is not a valid Kenyan mobile number.")
                continue
            if phone in seen:
                continue
            seen.add(phone)
            parsed.append((parts[0], phone))
        if errors:
            raise ValidationError(errors)
        self.parsed_new = parsed
        return raw

    def clean(self):
        cleaned = super().clean()
        if (
            not self.errors
            and not cleaned.get("farmers")
            and not self.parsed_new
            and not cleaned.get("group_photo")
        ):
            raise ValidationError("Select farmers, add new farmers, or upload the group photo.")
        return cleaned

    @transaction.atomic
    def save(self, registered_by):
        """Create attendance records; returns how many were newly registered."""
        group_photo = self.cleaned_data.get("group_photo")
        if group_photo:
            self.session.group_photo = group_photo
            self.session.save(update_fields=["group_photo"])

        farmers = list(self.cleaned_data.get("farmers", []))
        for name, phone in self.parsed_new:
            farmer, _ = Farmer.objects.get_or_create(
                phone=phone,
                defaults={
                    "full_name": name,
                    "county": self.session.county,
                    "registered_by": registered_by,
                },
            )
            farmers.append(farmer)
        created = 0
        for farmer in farmers:
            _, was_created = Attendance.objects.get_or_create(
                session=self.session,
                farmer=farmer,
                defaults={"registered_by": registered_by},
            )
            created += int(was_created)
        return created
