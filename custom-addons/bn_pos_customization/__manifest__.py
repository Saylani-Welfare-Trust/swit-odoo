{
    'name': 'POS Customization',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/POS Customization',
    'depends': [
        'bn_pos_custom_action',
        'bn_profile_management',
    ],
    'data': [
        'security/group.xml',
        'security/record_rule.xml',
        'views/pos_config.xml',
        'views/pos_session.xml',
        'views/pos_assets_index.xml',
    ],
    'auto_install': False,
    'application': False,
    'assets': {
        'point_of_sale._assets_pos': [
            'bn_pos_customization/static/src/override/app/**/*',
            # 'bn_pos_customization/static/src/override/screens/**/*',
            'bn_pos_customization/static/src/override/screens/order_receipt/order_receipt.xml',
            'bn_pos_customization/static/src/override/screens/partner_list/partner_list.js',
            'bn_pos_customization/static/src/override/screens/payment_screen/payment_screen.xml',
            'bn_pos_customization/static/src/override/screens/receipt_screen/receipt_screen.xml',
            'bn_pos_customization/static/src/override/models/**/*',
            'bn_pos_customization/static/src/scss/*',
            'bn_pos_customization/static/src/css/*',
        ],
    }
}