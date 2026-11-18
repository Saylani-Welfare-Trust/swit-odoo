{
    'name': 'Kitchen',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Kitchen',
    'depends': [
        'mrp',
        'stock',
    ],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        
        'data/sequence.xml',
        
        'views/ration_packing.xml',
        'views/issuance_request.xml',
        'views/kitchen_menu.xml',
        'views/branch_kitchen_request.xml',
        'views/product_template.xml',
    ],
    'auto_install': False,
    'application': True,
}