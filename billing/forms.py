from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError

from .models import Plan
from .money import ksh_to_minor_units, minor_units_to_ksh


class PackageSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(attrs={"class": "field", "placeholder": "Search packages"}),
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


class PlanForm(forms.ModelForm):
    price_ksh = forms.DecimalField(
        label="Price (KSh)",
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "field", "step": "0.01", "min": "0.01"}),
    )
    reason = forms.CharField(
        label="Reason",
        required=True,
        widget=forms.Textarea(attrs={"class": "field", "rows": 3}),
    )

    class Meta:
        model = Plan
        fields = [
            "name",
            "download_speed_mbps",
            "duration_days",
            "grace_period_hours",
            "description",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "field"}),
            "download_speed_mbps": forms.NumberInput(attrs={"class": "field", "min": "1"}),
            "duration_days": forms.NumberInput(attrs={"class": "field", "min": "1"}),
            "grace_period_hours": forms.NumberInput(attrs={"class": "field", "min": "0"}),
            "description": forms.Textarea(attrs={"class": "field", "rows": 4}),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and not self.is_bound:
            self.fields["price_ksh"].initial = minor_units_to_ksh(self.instance.price_minor)

    def clean_name(self) -> str:
        name = self.cleaned_data["name"].strip()
        if not name:
            raise ValidationError("Package name is required.")
        duplicate = Plan.objects.filter(name__iexact=name)
        if self.instance and self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise ValidationError("A package with this name already exists.")
        return name

    def clean_price_ksh(self):
        return ksh_to_minor_units(self.cleaned_data["price_ksh"])

    def clean(self):
        cleaned_data = super().clean()
        price_minor = cleaned_data.get("price_ksh")
        if price_minor is not None:
            self.instance.price_minor = price_minor
            self.instance.currency = "KES"
        return cleaned_data

    def save(self, commit: bool = True):
        plan = super().save(commit=False)
        plan.price_minor = self.cleaned_data["price_ksh"]
        plan.currency = "KES"
        if commit:
            plan.save()
        return plan


class SubscriptionPackageForm(forms.Form):
    plan = forms.ModelChoiceField(
        label="Package",
        queryset=Plan.objects.none(),
        widget=forms.Select(attrs={"class": "field"}),
    )
    reason = forms.CharField(
        label="Reason",
        required=True,
        widget=forms.Textarea(attrs={"class": "field", "rows": 3}),
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["plan"].queryset = Plan.objects.filter(is_active=True).order_by(
            "download_speed_mbps",
            "price_minor",
            "name",
        )

    def clean_reason(self) -> str:
        reason = self.cleaned_data["reason"].strip()
        if not reason:
            raise ValidationError("Reason is required.")
        return reason
