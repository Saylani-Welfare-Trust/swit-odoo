{
    'name': 'Kitchen',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/Kitchen',
    'depends': [
        'mrp',
        'stock',
    ],
    'data': [
        'data/sequence.xml',
        'security/ir.model.access.csv',
        'views/ration_packing.xml',
        'views/issuance_request.xml',
        'views/kitchen_menu.xml',
        'views/branch_kitchen_request.xml',
    ],
    'auto_install': False,
    'application': True,
}