{
    'name': 'Advance Donation Syncing',
    'version': '1.0',
    'description': 'Integration between Advance Donation and Welfare modules',
    'author': 'Muhammad Abdullah',
    'website': 'http://bytesnode.com',
    'category': 'BytesNode/Integration',
    'depends': [
        'bn_welfare',
        'bn_advance_donation',
        'bn_microfinance',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizaard/advance_donation_wizard.xml',
        'views/microfinance_views.xml',
        'views/advance_donation_line_views.xml',
        'views/welfare_line_views.xml',
        'views/welfare_recurring_line_views.xml',
    ],
    'license': 'AGPL-3',
    'installable': True,
    'application': False,
} # type: ignore
