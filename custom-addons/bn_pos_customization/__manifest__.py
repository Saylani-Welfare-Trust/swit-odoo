{
    'name': 'POS Customization',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/POS Customization',
    'depends': [
        'bn_pos_cheque',
        'bn_profile_management',
        'bn_analytic_account_customization'
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
            # 'bn_pos_customization/static/src/override/models/**/*',
            'bn_pos_customization/static/src/override/screens/**/*',
            'bn_pos_customization/static/src/override/store/**/*',
            'bn_pos_customization/static/src/scss/*',
            'bn_pos_customization/static/src/css/*',
        ],
    }
}