{
    'name': 'Treasury Dashboard',
    'version': '17.0.1.0.0',
    'category': 'Accounting/Treasury',
    'summary': 'A custom Treasury Dashboard for Odoo 17 Community',
    'depends': ['base', 'web', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/treasury_dashboard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'bn_treasury_dashboard/static/src/js/dashboard.js',
            'bn_treasury_dashboard/static/src/xml/dashboard.xml',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}