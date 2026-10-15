{
    'name': 'Treasury Dashboard',
    'version': '17.0.1.0.0',
    'category': 'Accounting/Treasury',
    'summary': 'A custom Treasury Dashboard for Odoo 17 Community',
    'description': """
        This module provides a Treasury Dashboard similar to the Accounting Dashboard.
        It includes KPI cards for Cash, Receivables, and Payables, along with a monthly chart.
    """,
    'depends': ['base', 'web', 'account'],
    'data': [
        'views/treasury_dashboard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'treasury_dashboard/static/src/js/dashboard.js',
            'treasury_dashboard/static/src/xml/dashboard.xml',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}