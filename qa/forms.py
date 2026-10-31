from django import forms

from core.forms import StyledFormMixin

from .models import QACall


class TrainingReviewForm(forms.Form):
    decision = forms.ChoiceField(
        choices=(
            ("approved", "Approve"),
            ("rejected", "Reject"),
        ),
        widget=forms.RadioSelect,
    )
    reason = forms.CharField(
        max_length=1000,
        strip=True,
        widget=forms.Textarea(attrs={"rows": 2, "class": "input"}),
    )


class QACallForm(StyledFormMixin, forms.ModelForm):
    outcome = forms.ChoiceField(choices=QACall.Outcome.choices, widget=forms.RadioSelect)
    rating = forms.TypedChoiceField(
        required=False,
        coerce=int,
        empty_value=None,
        choices=[("", "No rating")] + [(i, str(i)) for i in range(1, 6)],
        label="Training rating (1-5)",
    )

    class Meta:
        model = QACall
        fields = ("outcome", "rating", "feedback", "farmer_question")
        widgets = {
            "feedback": forms.Textarea(attrs={"rows": 3}),
            "farmer_question": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        # Rating, feedback and questions only make sense if the farmer attended.
        if cleaned.get("outcome") != QACall.Outcome.CONFIRMED:
            cleaned["rating"] = None
            cleaned["feedback"] = ""
            cleaned["farmer_question"] = ""
        return cleaned
