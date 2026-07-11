from __future__ import annotations

ROLE_OWNER = "Owner"
ROLE_ADMINISTRATOR = "Administrator"
ROLE_FINANCE = "Finance"
ROLE_NOC = "NOC"
ROLE_SUPPORT = "SuperSurf Support"
ROLE_READ_ONLY = "Read Only"

ROLE_NAMES = [
    ROLE_OWNER,
    ROLE_ADMINISTRATOR,
    ROLE_FINANCE,
    ROLE_NOC,
    ROLE_SUPPORT,
    ROLE_READ_ONLY,
]

ROLE_PERMISSION_CODENAMES = {
    ROLE_OWNER: ["*"],
    ROLE_ADMINISTRATOR: [
        "core.view_organization",
        "core.change_organization",
        "core.view_organizationbranding",
        "core.change_organizationbranding",
        "users.view_user",
        "users.change_user",
        "users.assign_roles",
        "audit.view_auditevent",
        "billing.view_plan",
        "billing.add_plan",
        "billing.change_plan",
    ],
    ROLE_FINANCE: [
        "core.view_organization",
        "core.view_organizationbranding",
        "audit.view_auditevent",
        "billing.view_plan",
    ],
    ROLE_NOC: [
        "core.view_organization",
        "core.view_organizationbranding",
        "audit.view_auditevent",
        "billing.view_plan",
    ],
    ROLE_SUPPORT: [
        "core.view_organization",
        "core.view_organizationbranding",
        "users.view_user",
        "billing.view_plan",
    ],
    ROLE_READ_ONLY: [
        "core.view_organization",
        "core.view_organizationbranding",
        "users.view_user",
        "audit.view_auditevent",
        "billing.view_plan",
    ],
}


def is_owner(user) -> bool:
    return bool(user and user.is_authenticated and user.groups.filter(name=ROLE_OWNER).exists())
