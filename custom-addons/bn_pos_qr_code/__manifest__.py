{
    'name': 'QR Code | POS',
    'version': '1.0',
    'summary': 'Open QR Code model when click on QR Code in Payments',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/QR Code | POS',
    'depends': [
        'point_of_sale'
    ],
    'data': [
        'views/pos_order.xml'
    ],
    'auto_install': False,
    'application': False,
    'assets': {
        'point_of_sale._assets_pos': [
            'bn_pos_qr_code/static/src/js/pos_model.js',
            'bn_pos_qr_code/static/src/xml/qr_code_popup.xml',
            'bn_pos_qr_code/static/src/js/qr_code_popup.js',
        ]
    }
}