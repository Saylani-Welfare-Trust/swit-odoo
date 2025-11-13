{
    'name': 'Master Setup',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Master Setup',
    'depends': [
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/group.xml',
        'views/location_option.xml',
        'views/installation_category.xml',
        'views/header_type.xml',
        'views/gateway_config.xml',
        'views/microfinance_scheme.xml',
    ],
    'auto_install': False,
    'application': True,
}