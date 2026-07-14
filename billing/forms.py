from __future__ import annotations

import uuid

from django import forms
from django.core.exceptions import ValidationError

from subscribers.models import Subscriber

from .models import MAX_MONEY_MINOR, LedgerEntry, MpesaCallbackEvent, PaymentProviderProfile, Plan
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


class BillingPeriodActionForm(forms.Form):
    operation_id = forms.UUIDField(widget=forms.HiddenInput)
    expected_previous_period_id = forms.CharField(required=False, widget=forms.HiddenInput)
    reason = forms.CharField(
        label="Reason",
        required=True,
        max_length=240,
        widget=forms.Textarea(attrs={"class": "field", "rows": 2}),
    )

    def __init__(self, *args, **kwargs) -> None:
        initial = kwargs.setdefault("initial", {})
        initial.setdefault("operation_id", uuid.uuid4())
        super().__init__(*args, **kwargs)

    def clean_expected_previous_period_id(self) -> str:
        value = self.cleaned_data["expected_previous_period_id"].strip()
        if not value:
            return ""
        try:
            uuid.UUID(value)
        except ValueError as exc:
            raise ValidationError("Expected previous billing period is not valid.") from exc
        return value

    def clean_reason(self) -> str:
        reason = self.cleaned_data["reason"].strip()
        if not reason:
            raise ValidationError("Reason is required.")
        return reason


class WalletAdjustmentForm(forms.Form):
    operation_id = forms.UUIDField(widget=forms.HiddenInput)
    direction = forms.ChoiceField(choices=LedgerEntry.DIRECTION_CHOICES, widget=forms.HiddenInput)
    amount_ksh = forms.DecimalField(
        label="Amount (KSh)",
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "field", "step": "0.01", "min": "0.01"}),
    )
    reason = forms.CharField(
        label="Reason",
        required=True,
        max_length=240,
        widget=forms.Textarea(attrs={"class": "field", "rows": 2}),
    )

    def __init__(self, *args, **kwargs) -> None:
        initial = kwargs.setdefault("initial", {})
        initial.setdefault("operation_id", uuid.uuid4())
        super().__init__(*args, **kwargs)

    def clean_amount_ksh(self):
        amount = self.cleaned_data["amount_ksh"]
        amount_minor = ksh_to_minor_units(amount)
        if amount_minor > MAX_MONEY_MINOR:
            raise ValidationError("Amount is too large.")
        return amount

    def clean_reason(self) -> str:
        reason = self.cleaned_data["reason"].strip()
        if not reason:
            raise ValidationError("Reason is required.")
        return reason


class LedgerReversalForm(forms.Form):
    operation_id = forms.UUIDField(widget=forms.HiddenInput)
    reason = forms.CharField(
        label="Reason",
        required=True,
        max_length=240,
        widget=forms.Textarea(attrs={"class": "field", "rows": 2}),
    )

    def __init__(self, *args, **kwargs) -> None:
        initial = kwargs.setdefault("initial", {})
        initial.setdefault("operation_id", uuid.uuid4())
        super().__init__(*args, **kwargs)

    def clean_reason(self) -> str:
        reason = self.cleaned_data["reason"].strip()
        if not reason:
            raise ValidationError("Reason is required.")
        return reason


class PaymentSearchForm(forms.Form):
    STATUS_CHOICES = [
        ("", "All"),
        ("allocated", "Allocated"),
        ("unmatched", "Unmatched"),
    ]

    q = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(
            attrs={
                "class": "field",
                "placeholder": "Transaction ID, account reference, or subscriber account",
            }
        ),
    )
    status = forms.ChoiceField(
        required=False,
        choices=STATUS_CHOICES,
        widget=forms.Select(attrs={"class": "field"}),
    )
    provider_profile = forms.ModelChoiceField(
        required=False,
        label="Provider profile",
        queryset=PaymentProviderProfile.objects.none(),
        widget=forms.Select(attrs={"class": "field"}),
    )
    date_from = forms.DateField(
        required=False,
        label="From",
        widget=forms.DateInput(attrs={"class": "field", "type": "date"}),
    )
    date_to = forms.DateField(
        required=False,
        label="To",
        widget=forms.DateInput(attrs={"class": "field", "type": "date"}),
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["provider_profile"].queryset = PaymentProviderProfile.objects.order_by(
            "provider",
            "product_type",
            "environment",
            "name",
        )


class MpesaCallbackEventSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(
            attrs={
                "class": "field",
                "placeholder": "Transaction, CheckoutRequestID, MerchantRequestID, or reference",
            }
        ),
    )
    event_type = forms.ChoiceField(
        required=False,
        label="Event type",
        choices=[("", "All"), *MpesaCallbackEvent.EVENT_TYPE_CHOICES],
        widget=forms.Select(attrs={"class": "field"}),
    )
    result_code = forms.CharField(
        required=False,
        label="Result code",
        max_length=16,
        widget=forms.TextInput(attrs={"class": "field"}),
    )
    date_from = forms.DateField(
        required=False,
        label="From",
        widget=forms.DateInput(attrs={"class": "field", "type": "date"}),
    )
    date_to = forms.DateField(
        required=False,
        label="To",
        widget=forms.DateInput(attrs={"class": "field", "type": "date"}),
    )


class FakePaymentIngestionForm(forms.Form):
    operation_id = forms.UUIDField(widget=forms.HiddenInput)
    provider_profile = forms.ModelChoiceField(
        label="Provider profile",
        queryset=PaymentProviderProfile.objects.none(),
        widget=forms.Select(attrs={"class": "field"}),
    )
    provider_transaction_id = forms.CharField(
        label="Provider transaction ID",
        max_length=128,
        widget=forms.TextInput(attrs={"class": "field"}),
    )
    amount_ksh = forms.DecimalField(
        label="Amount (KSh)",
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "field", "step": "0.01", "min": "0.01"}),
    )
    received_at = forms.DateTimeField(
        label="Received at",
        widget=forms.DateTimeInput(attrs={"class": "field", "type": "datetime-local"}),
    )
    account_reference = forms.CharField(
        label="Account reference",
        required=False,
        max_length=64,
        widget=forms.TextInput(attrs={"class": "field", "placeholder": "SS000001"}),
    )
    payload_digest = forms.CharField(
        label="Payload digest",
        required=False,
        max_length=64,
        widget=forms.TextInput(attrs={"class": "field"}),
    )

    def __init__(self, *args, **kwargs) -> None:
        initial = kwargs.setdefault("initial", {})
        initial.setdefault("operation_id", uuid.uuid4())
        super().__init__(*args, **kwargs)
        self.fields["provider_profile"].queryset = PaymentProviderProfile.objects.filter(
            is_active=True,
            provider=PaymentProviderProfile.PROVIDER_FAKE,
            product_type=PaymentProviderProfile.PRODUCT_FAKE,
            environment__in=[
                PaymentProviderProfile.ENVIRONMENT_TEST,
                PaymentProviderProfile.ENVIRONMENT_SANDBOX,
            ],
        ).order_by("environment", "name")

    def clean_provider_transaction_id(self) -> str:
        value = self.cleaned_data["provider_transaction_id"].strip()
        if not value:
            raise ValidationError("Provider transaction ID is required.")
        return value

    def clean_amount_ksh(self):
        amount = self.cleaned_data["amount_ksh"]
        amount_minor = ksh_to_minor_units(amount)
        if amount_minor > MAX_MONEY_MINOR:
            raise ValidationError("Amount is too large.")
        return amount

    def clean_account_reference(self) -> str:
        return self.cleaned_data["account_reference"].strip()

    def clean_payload_digest(self) -> str:
        return self.cleaned_data["payload_digest"].strip().lower()


class ResolveUnmatchedPaymentForm(forms.Form):
    operation_id = forms.UUIDField(widget=forms.HiddenInput)
    subscriber = forms.ModelChoiceField(
        label="Subscriber",
        queryset=Subscriber.objects.none(),
        widget=forms.Select(attrs={"class": "field"}),
    )
    reason = forms.CharField(
        label="Resolution reason",
        required=True,
        max_length=240,
        widget=forms.Textarea(attrs={"class": "field", "rows": 3}),
    )

    def __init__(self, *args, **kwargs) -> None:
        initial = kwargs.setdefault("initial", {})
        initial.setdefault("operation_id", uuid.uuid4())
        super().__init__(*args, **kwargs)
        self.fields["subscriber"].queryset = Subscriber.objects.order_by("account_number")

    def clean_reason(self) -> str:
        reason = self.cleaned_data["reason"].strip()
        if not reason:
            raise ValidationError("Reason is required.")
        return reason
