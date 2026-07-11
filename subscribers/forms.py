from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError

from .models import Service, Subscriber
from .phone import normalize_kenyan_phone


class SubscriberSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(
            attrs={
                "class": "field",
                "placeholder": "Search account, name, phone, or service reference",
            }
        ),
    )
    status = forms.ChoiceField(
        required=False,
        choices=[
            ("", "All"),
            ("active", "Active"),
            ("inactive", "Inactive"),
        ],
        widget=forms.Select(attrs={"class": "field"}),
    )

    def __init__(self, *args, can_view_services: bool = False, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if not can_view_services:
            self.fields["q"].widget.attrs["placeholder"] = "Search account, name, or phone"


class SubscriberForm(forms.ModelForm):
    reason = forms.CharField(
        label="Reason",
        required=True,
        widget=forms.Textarea(attrs={"class": "field", "rows": 3}),
    )

    class Meta:
        model = Subscriber
        fields = ["customer_type", "display_name", "primary_phone", "email"]
        widgets = {
            "customer_type": forms.Select(attrs={"class": "field"}),
            "display_name": forms.TextInput(attrs={"class": "field"}),
            "primary_phone": forms.TextInput(attrs={"class": "field", "autocomplete": "tel"}),
            "email": forms.EmailInput(attrs={"class": "field", "autocomplete": "email"}),
        }

    def clean_display_name(self) -> str:
        display_name = self.cleaned_data["display_name"].strip()
        if not display_name:
            raise ValidationError("Display name is required.")
        return display_name

    def clean_primary_phone(self) -> str:
        return normalize_kenyan_phone(self.cleaned_data["primary_phone"])

    def clean_email(self) -> str:
        return self.cleaned_data.get("email", "").strip()


class ServiceForm(forms.ModelForm):
    reason = forms.CharField(
        label="Reason",
        required=True,
        widget=forms.Textarea(attrs={"class": "field", "rows": 3}),
    )

    class Meta:
        model = Service
        fields = ["label"]
        widgets = {
            "label": forms.TextInput(attrs={"class": "field"}),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["label"].required = False

    def clean_label(self) -> str:
        return self.cleaned_data.get("label", "").strip()
