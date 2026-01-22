{
    'name': 'POS Closing Session',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/POS Closing Session',
    'depends': [
        'point_of_sale'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/pos_order.xml',
        'views/pos_payment_method.xml',
        'views/res_company.xml',
        'views/res_config_setting.xml',
        'views/pos_session_slip.xml',
        'views/pos_session.xml',
        'views/account_journal.xml',
    ],
    'auto_install': False,
    'application': False,
    'assets': {
        'point_of_sale._assets_pos': [
            'bn_closing_session/static/src/app/**/*',
            'bn_closing_session/static/src/models/navbar.js',
        ]
    }
}