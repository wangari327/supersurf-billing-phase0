from __future__ import annotations

from django import forms
from django.contrib.auth.models import Group

from .models import User
from .roles import ROLE_NAMES


class StaffSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(attrs={"class": "field"}),
    )


class RoleAssignmentForm(forms.Form):
    roles = forms.ModelMultipleChoiceField(
        queryset=Group.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"class": "field", "rows": 3}),
        required=True,
        help_text="Required for role changes.",
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["roles"].queryset = Group.objects.filter(name__in=ROLE_NAMES).order_by("name")


class StaffProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["display_name", "first_name", "last_name", "email", "is_active"]
        widgets = {
            "display_name": forms.TextInput(attrs={"class": "field"}),
            "first_name": forms.TextInput(attrs={"class": "field"}),
            "last_name": forms.TextInput(attrs={"class": "field"}),
            "email": forms.EmailInput(attrs={"class": "field"}),
        }
