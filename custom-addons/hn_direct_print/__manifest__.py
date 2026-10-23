{
    'name': 'Direct Print for Odoo QZ',
    'version': '17.0.0.1',
    'category': 'Printing',
    'summary': "Connect Odoo with QZ Tray for Direct Printing",
    'description': "",
    'author': 'Hamza Naveed',
    'website': "https://www.linkedin.com/in/sm-hamza-naveed/",
    'depends': ['web'],
    'data': [
        'views/res_users_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            "hn_direct_print/static/src/js/print.js",
            # "hn_direct_print/static/src/js/qz_autoprint.js",
            # "hn_direct_print/static/lib/qz/qz-tray.js",
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False,
}
