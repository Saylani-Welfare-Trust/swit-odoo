{
    'name': 'Planning',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'http://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/Planning',
    'depends': [
        'mail',
        'product',
        'bn_kitchen',
    ],
    'data': [
        'data/stock_location.xml',
        'security/ir.model.access.csv',
        'views/daily_planning.xml',
    ],
    'auto_install': False,
    'application': True,
}