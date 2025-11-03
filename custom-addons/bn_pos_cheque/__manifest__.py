{
    'name': 'POS Cheque',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/POS Cheque',
    'depends': [
        'account',
        'bn_pos_custom_action',
    ],
    'data': [
        'security/group.xml',
        'security/ir.model.access.csv',
        'views/pos_cheque.xml',
        'views/pos_order.xml',
    ],
    'auto_install': False,
    'application': False,
    'assets': {
        'point_of_sale._assets_pos': [
            'bn_pos_cheque/static/src/app/**/*',
            'bn_pos_cheque/static/src/models/*',
        ],
    }
}