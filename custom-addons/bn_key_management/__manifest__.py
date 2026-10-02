{
    'name': 'Key Management',
    'version': '17.0.1.1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Key Management',
    'depends': [
        'bn_donation_box'
    ],
    'data': [
        'data/schedule_action.xml',
        'data/ir_module_category.xml',
        'security/groups.xml',
        'security/ir.model.access.csv',
        'wizards/bulk_key_issuance.xml',
        'wizards/manual_key_issuance.xml',
        'views/key.xml',
        'views/key_bunch.xml',
        'views/key_issuance.xml',
        'views/donation_box_request.xml',
        'views/donation_box_registration_installation.xml'
    ],
    'auto_install': False,
    'application': False,
    'assets': {
        'point_of_sale._assets_pos': [
            'bn_key_management/static/src/app/**/*',
            'bn_key_management/static/src/screen/*',
        ],
    },
}