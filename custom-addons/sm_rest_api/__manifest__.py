{
    "name": "Custom Rest API",
    "summary": """
       Custom Rest API
    """,
    "description": """
        Custom Rest API
    """,
    "category": "TechnoCoderSol/RestAPI",
    "author": "Shariq Ali Mehdi",
    "version": "17.0",
    'license': 'OPL-1',
    'depends': ['base', 'web', 'bn_import_donation'],
    "data": [
        'security/ir.model.access.csv',
        'data/donation_authorization_data.xml',
        'views/donation_authorization_view.xml',
        'views/donation_data_view.xml',
        'wizard/import_donation_wizard.xml',
        'reports/donation.xml',
    ],
    "application": False,
    "installable": True,
    "auto_install": False,
}
