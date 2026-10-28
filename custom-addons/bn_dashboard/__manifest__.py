{
    'name': 'Treasury Dashboard',
    'version': '17.0.1.0.0',
    'category': 'Accounting/BytesNode',
    'author': 'Abdul Hai',
    'summary': 'A custom Dashboard for Odoo 17 Community',
    'depends': ['base', 'web', 'account', 'bn_pos_cheque','bn_donation_box','bn_profile_management','hr',],
    'data': [
        'security/ir.model.access.csv',
        'views/treasury_dashboard_views.xml',
        'views/donation_box_dashboard_views.xml',
        'views/profile_management_dashboard_views.xml',
        'views/pos_order_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'bn_treasury_dashboard/static/src/js/treasury_dashboard.js',
            'bn_treasury_dashboard/static/src/xml/treasury_dashboard.xml',
            'bn_treasury_dashboard/static/src/js/donation_box_dashboard.js',
            'bn_treasury_dashboard/static/src/xml/donation_box_dashboard.xml',
            'bn_treasury_dashboard/static/src/js/profile_management_dashboard.js',
            'bn_treasury_dashboard/static/src/xml/profile_management_dashboard.xml',
            'bn_treasury_dashboard/static/src/xml/pos_dashboard.xml',
            'bn_treasury_dashboard/static/src/js/pos_dashboard.js',
            'bn_treasury_dashboard/static/src/css/pos_dashboard.css',
            'bn_treasury_dashboard/static/src/css/pos_dashboard_v2.scss',
            'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js'
        ],
    },
    'external_dependencies': {
            'python': ['pandas'],
        },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}