from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.db import transaction

from core.forms import KenyanPhoneField, StyledFormMixin
from training.models import County, Farmer

from .models import User


class StyledAuthenticationForm(StyledFormMixin, AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.is_farmer:
            raise ValidationError(
                "Farmers should sign in through the farmer sign-in page.",
                code="invalid_login",
            )


class FarmerAuthenticationForm(StyledAuthenticationForm):
    def confirm_login_allowed(self, user):
        if not user.is_active:
            raise ValidationError(self.error_messages["inactive"], code="inactive")
        if not user.is_farmer:
            raise ValidationError(
                "This sign-in page is for farmer accounts.",
                code="invalid_login",
            )


class FarmerSignUpForm(StyledFormMixin, UserCreationForm):
    phone = KenyanPhoneField(label="Mobile phone")
    county = forms.ModelChoiceField(queryset=County.objects.none())

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "phone")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["username"].label = "Choose a username"
        self.fields["county"].queryset = County.objects.all()
        self.order_fields(
            (
                "first_name",
                "last_name",
                "phone",
                "county",
                "username",
                "email",
                "password1",
                "password2",
            )
        )

    def clean_phone(self):
        phone = self.cleaned_data["phone"]
        if Farmer.objects.filter(phone=phone).exists():
            raise forms.ValidationError(
                "This phone is already on a training record. Contact Digicow to verify "
                "and connect that record to your account."
            )
        if User.objects.filter(phone=phone).exists():
            raise forms.ValidationError("An account already uses this phone number.")
        return phone

    @transaction.atomic
    def save(self, commit=True):
        if not commit:
            raise ValueError("Farmer sign-up must save the account and farmer profile together.")

        user = super().save(commit=False)
        user.role = User.Role.FARMER
        user.phone = self.cleaned_data["phone"]
        user.save()
        Farmer.objects.create(
            full_name=user.get_full_name(),
            phone=user.phone,
            county=self.cleaned_data["county"],
            user=user,
        )
        return user


class StyledPasswordChangeForm(StyledFormMixin, PasswordChangeForm):
    pass


class StaffCreateForm(StyledFormMixin, UserCreationForm):
    """Lets a coordinator add trainers, Q&A agents and other coordinators."""

    phone = KenyanPhoneField(required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "phone", "role")

    def __init__(self, *args, creator=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["role"].choices = [
            (value, label)
            for value, label in User.Role.choices
            if value != User.Role.FARMER
            and (value != User.Role.ADMIN or creator and creator.is_admin)
        ]
