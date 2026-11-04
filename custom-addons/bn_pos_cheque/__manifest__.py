{
    'name': 'POS Cheque',
    'version': '17.0.1.2.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/POS Cheque',
    'depends': [
        'account',
        'bn_closing_session',
        'bn_pos_custom_action',
        'bn_pos_order',
        'bn_sms_whatsapp',
    ],
    'data': [
        'security/group.xml',
        'security/ir.model.access.csv',
        
        'reports/pos_order_receipt.xml',
        
        'views/pos_cheque.xml',
        'views/pos_order.xml',
        'views/res_config_settings.xml',

        'data/res_company.xml',
    ],
    'auto_install': False,
    'application': False,
    'assets': {
        'point_of_sale._assets_pos': [
            'bn_pos_cheque/static/src/app/**/*',
            'bn_pos_cheque/static/src/screens/**/*',
            'bn_pos_cheque/static/src/models/*',
        ],
    }
}