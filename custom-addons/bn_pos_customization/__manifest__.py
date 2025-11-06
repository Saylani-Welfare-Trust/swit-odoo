{
    'name': 'POS Customization',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/POS Customization',
    'depends': [
        'point_of_sale',
        'bn_profile_management'
    ],
    'data': [
        'security/group.xml',
        'security/record_rule.xml',
        'views/pos_config.xml',
    ],
    'auto_install': False,
    'application': False,
    'assets': {
        'point_of_sale._assets_pos': [
            'bn_pos_customization/static/src/override/app/**/*',
        ],
    }
}