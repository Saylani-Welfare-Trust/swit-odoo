{
    'name': 'Treasury Dashboard',
    'version': '17.0.1.0.0',
    'category': 'Accounting/BytesNode',
    'author': 'Abdul Hai',
    'summary': 'A custom Treasury Dashboard for Odoo 17 Community',
    'depends': ['base', 'web', 'account', 'bn_pos_cheque','bn_donation_box'],
    'data': [
        'security/ir.model.access.csv',
        'views/treasury_dashboard_views.xml',
        'views/donation_box_dashboard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'bn_treasury_dashboard/static/src/js/dashboard.js',
            'bn_treasury_dashboard/static/src/xml/dashboard.xml',
            'bn_treasury_dashboard/static/src/js/donation_box_dashboard.js',
            'bn_treasury_dashboard/static/src/js/donation_box_dashboard.xml',
            
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}