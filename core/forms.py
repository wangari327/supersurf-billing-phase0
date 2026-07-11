from __future__ import annotations

from django import forms

from .models import Organization, OrganizationBranding


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = [
            "primary_brand",
            "trading_name",
            "product_name",
            "network_label",
            "support_label",
            "portal_label",
            "registered_business_name",
            "domain",
            "support_email",
            "billing_email",
            "noc_email",
            "support_phone",
            "paybill_number",
            "till_number",
            "kra_pin",
            "registration_number",
            "communications_authority_licence",
        ]
        widgets = {
            "primary_brand": forms.TextInput(attrs={"class": "field"}),
            "trading_name": forms.TextInput(attrs={"class": "field"}),
            "product_name": forms.TextInput(attrs={"class": "field"}),
            "network_label": forms.TextInput(attrs={"class": "field"}),
            "support_label": forms.TextInput(attrs={"class": "field"}),
            "portal_label": forms.TextInput(attrs={"class": "field"}),
            "registered_business_name": forms.TextInput(attrs={"class": "field"}),
            "domain": forms.TextInput(attrs={"class": "field"}),
            "support_email": forms.EmailInput(attrs={"class": "field"}),
            "billing_email": forms.EmailInput(attrs={"class": "field"}),
            "noc_email": forms.EmailInput(attrs={"class": "field"}),
            "support_phone": forms.TextInput(attrs={"class": "field"}),
            "paybill_number": forms.TextInput(attrs={"class": "field"}),
            "till_number": forms.TextInput(attrs={"class": "field"}),
            "kra_pin": forms.TextInput(attrs={"class": "field"}),
            "registration_number": forms.TextInput(attrs={"class": "field"}),
            "communications_authority_licence": forms.TextInput(attrs={"class": "field"}),
        }


class BrandingForm(forms.ModelForm):
    class Meta:
        model = OrganizationBranding
        fields = [
            "primary_ui_colour",
            "secondary_ui_colour",
            "receipt_heading",
            "invoice_heading",
            "receipt_footer",
            "invoice_footer",
            "payment_instructions",
        ]
        widgets = {
            "primary_ui_colour": forms.TextInput(attrs={"class": "field", "type": "color"}),
            "secondary_ui_colour": forms.TextInput(attrs={"class": "field", "type": "color"}),
            "receipt_heading": forms.TextInput(attrs={"class": "field"}),
            "invoice_heading": forms.TextInput(attrs={"class": "field"}),
            "receipt_footer": forms.Textarea(attrs={"class": "field", "rows": 3}),
            "invoice_footer": forms.Textarea(attrs={"class": "field", "rows": 3}),
            "payment_instructions": forms.Textarea(attrs={"class": "field", "rows": 3}),
        }
