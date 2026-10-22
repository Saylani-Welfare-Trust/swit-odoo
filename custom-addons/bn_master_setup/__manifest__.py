{
    'name': 'Master Setup',
    'version': '17.0.1.1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Master Setup',
    'depends': [
        'base',
        'mail',
    ],
    'data': [
        'data/ir_module_category.xml',
        'security/group.xml',
        'security/ir.model.access.csv',
        'views/menu.xml',
        'views/city.xml',
        'views/bank.xml',
    ],
    'auto_install': False,
    'application': True,
} # type: ignore