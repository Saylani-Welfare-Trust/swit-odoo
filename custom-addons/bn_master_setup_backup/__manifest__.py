{
    'name': 'Master Setup Backup',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Master Setup Backup',
    'depends': [
        'bn_analytic_account_customization'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/sub_zone.xml',
    ],
    'auto_install': False,
    'application': False,
}