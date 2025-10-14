{
    'name': 'Master Setup',
    'version': '1.0',
    'summary': 'Master Setups',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Master Setup',
    'depends': [
        'base',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/installation_category.xml',
        'views/sub_zone.xml',
        'views/location_type.xml',
        'views/res_company.xml',
        'views/res_city.xml',
    ],
    'auto_install': False,
    'application': False,
}