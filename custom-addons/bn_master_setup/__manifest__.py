{
    'name': 'Master Setup',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Master Setup',
    'depends': [
        'base',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/group.xml',
        'views/menu.xml',
        'views/city.xml',
        'views/bank.xml',
    ],
    'auto_install': False,
    'application': True,
}