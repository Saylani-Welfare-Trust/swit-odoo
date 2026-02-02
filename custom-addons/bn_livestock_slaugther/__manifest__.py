{
    'name': 'Livestock Slaugther',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'http://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/Livestock Slaugther',
    'depends': [
        'stock',
        'mail'
    ],
    'data': [
        'data/stock_location.xml',
        'security/ir.model.access.csv',
        'views/livestock_slaugther.xml',
        'views/livestock_cutting.xml',
        'wizards/livestock_slaugther.xml',
    ],
    'auto_install': False,
    'application': True,
}