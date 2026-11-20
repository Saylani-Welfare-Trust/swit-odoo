{
    'name': 'POS Closing Session',
    'version': '17.0.1.3.1',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/POS Closing Session',
    'depends': ['bn_pos_custom_action', 
        'point_of_sale'
    ],
    'data': [
        'security/ir.model.access.csv', 'security/record_rule.xml',
        
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