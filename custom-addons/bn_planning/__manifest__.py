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
        'data/sequence_data.xml',
        'data/stock_location.xml',
        'security/ir.model.xml',  # Load models first
        'security/ir.model.access.csv',
        'views/daily_planning.xml',
        'views/monthly_planning_views.xml',
    ],
    'auto_install': False,
    'application': True,
}