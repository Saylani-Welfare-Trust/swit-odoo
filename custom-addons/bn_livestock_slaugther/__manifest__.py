{
    'name': 'Livestock Slaugther',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'http://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/Livestock Slaugther',
    'depends': [
        'stock',
        'mail',
        'bn_master_setup',
    ],
    'data': [
        'data/stock_location.xml',
        'security/ir.model.access.csv',
        'views/livestock_slaugther.xml',
        'views/livestock_cutting.xml',
        'views/livestock_cutting_material.xml',
        'wizards/livestock_slaugther.xml',
    ],
    'auto_install': False,
    'application': True,
}