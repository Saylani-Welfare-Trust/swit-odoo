{
    'name': 'Master Setup',
    'version': '17.0.1.3.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com',
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
        'data/bn_absorb.xml',
        'data/ir_module_category.xml',
        'security/group.xml',
        'security/ir.model.access.csv',
        
        
        'views/menu.xml',
        'views/city.xml',
        'views/bank.xml',
        'views/area.xml',
        'views/res_company.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'bn_master_setup/static/src/js/chatter.js',
        ],
    },
    'auto_install': False,
    'application': True,
} # type: ignore
