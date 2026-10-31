from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory

from core.forms import StyledFormMixin
from training.models import Farmer, TrainingSession

from .models import Order, OrderItem, Product


class ProductChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, product):
        return f"{product.brand.name} - {product.name} ({product.unit}) - KES {product.price:,.0f}"


class OrderForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Order
        fields = ("farmer", "session", "delivery_location", "notes")
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["farmer"].queryset = Farmer.objects.select_related("county").order_by(
            "full_name"
        )
        sessions = TrainingSession.objects.select_related("topic", "county")
        if not user.is_admin:
            sessions = sessions.filter(trainer=user)
        self.fields["session"].queryset = sessions
        self.fields["session"].required = False
        self.fields["session"].empty_label = "Not linked to a session"


class OrderItemForm(StyledFormMixin, forms.ModelForm):
    product = ProductChoiceField(
        queryset=Product.objects.filter(active=True, brand__active=True).select_related("brand"),
        empty_label="Choose a product",
    )

    class Meta:
        model = OrderItem
        fields = ("product", "quantity")
        widgets = {"quantity": forms.NumberInput(attrs={"min": 1, "placeholder": "Qty"})}


class BaseOrderItemFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        seen = set()
        for form in self.forms:
            product = form.cleaned_data.get("product")
            if not product:
                continue
            if product.pk in seen:
                raise ValidationError(
                    f"{product.name} appears more than once. Combine it into one line."
                )
            seen.add(product.pk)


OrderItemFormSet = inlineformset_factory(
    Order,
    OrderItem,
    form=OrderItemForm,
    formset=BaseOrderItemFormSet,
    extra=3,
    min_num=1,
    validate_min=True,
    can_delete=False,
)
