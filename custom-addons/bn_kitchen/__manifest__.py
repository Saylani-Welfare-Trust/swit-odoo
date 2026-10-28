{
    'name': 'Kitchen',
    'version': '17.0.1.3.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Kitchen',
    'depends': [
        'bn_stock_location',
        'mrp',
        'stock',
    ],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'security/stock_scope_rule.xml',
        
        'data/sequence.xml',
        
        'views/ration_packing.xml',
        'views/issuance_request.xml',
        'views/kitchen_menu.xml',
        'views/branch_kitchen_request.xml',
        'views/product_template.xml',
        'data/bn_program_types.xml',
    ],
    'auto_install': False,
    'application': True,
}