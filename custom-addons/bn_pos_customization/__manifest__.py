{
    'name': 'POS Customization',
    'version': '17.0.1.1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/POS Customization',
    'depends': [
        'bn_analytic_account_customization',
        'bn_pos_custom_action',
        'contacts',
    ],
    'data': [
        'data/ir_module_category.xml',
        'security/group.xml',
        'security/record_rule.xml',
        'views/pos_assets_index.xml',
    ],
    'auto_install': False,
    'application': False,
    'assets': {
        'point_of_sale._assets_pos': [
            'bn_pos_customization/static/src/override/app/**/*',
            'bn_pos_customization/static/src/override/screens/**/*',
            'bn_pos_customization/static/src/override/models/**/*',
            'bn_pos_customization/static/src/scss/*',
            'bn_pos_customization/static/src/css/*',
        ],
    }
}