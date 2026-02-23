{
    'name': 'Inventory Customization',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'http://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/Inventory Customization',
    'depends': [
        'stock',
        'bn_donation_home_service',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_picking.xml',
        'views/product_template.xml',
        'views/product_product.xml',
        'wizards/receive_by_weight.xml',
    ],
    'auto_install': False,
    'application': False,
}