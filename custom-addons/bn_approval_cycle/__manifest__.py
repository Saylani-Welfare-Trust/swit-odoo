{
    "name": "Approval Cycle",
    "summary": "Configurable sequential approval workflows for Odoo",
    "version": "18.0.2.9.0",
    "category": "BytesNode",
    "author": "Syed Owais Noor",
    "website": "https://bytesnode.com/",
    "license": "LGPL-3",
    "depends": ["base", "mail", "hr"],
    "data": [
        "security/approval_security.xml",
        "security/ir.model.access.csv",
        "data/approval_role_data.xml",
        "views/res_config_settings_views.xml",
        "views/approval_role_views.xml",
        "views/approval_rule_views.xml",
        "views/approval_request_views.xml",
        "wizard/approval_reject_wizard_views.xml",
        "views/approval_menus.xml"
    ],
    "application": True,
    "installable": True
}