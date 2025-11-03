{
    'name': 'POS Payment Method Customization',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/POS Payment Method Customization',
    'depends': [
        'bn_pos_cheque'
    ],
    'data': [
        'views/pos_payment_method.xml'
    ],
    'auto_install': False,
    'application': False,
    'assets': {
        'point_of_sale._assets_pos': [
            'bn_pos_payment_method/static/src/app/payment_popup/payment_popup.js',
            'bn_pos_payment_method/static/src/app/payment_popup/payment_popup.xml',
            'bn_pos_payment_method/static/src/components/**/*',
        ],
    }
}