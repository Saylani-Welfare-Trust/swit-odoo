{
    'name': 'Master Setup',
    'version': '1.1',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Master Setup',
    'depends': [
        'base',
        'mail',
        'product',
        'stock',
        'account',
    ],
    'data': [
        'data/ir_module_category.xml',
        'security/group.xml',
        'security/ir.model.access.csv',
        'data/mail_activity_type.xml',
        'views/source_document.xml',
        
        
        'views/menu.xml',
        'views/city.xml',
        'views/bank.xml',
        'views/area.xml',
    ],
    'auto_install': False,
    'application': True,
} # type: ignore
