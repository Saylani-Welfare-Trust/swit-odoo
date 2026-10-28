{
    'name': 'Stock Location Customization',
    'version': '17.0.1.4.0',
    'author': 'Syed Owais Noor',
    'website': '',
    'license': 'LGPL-3',
    'category': 'BytesNode/Stock Location Customization',
    'depends': [
        'mrp',
        'sale_stock',
        'purchase_requisition',
        'stock',
        'bn_pos_customization',
        'bn_analytic_account_customization'
    ],
    'data': [
        'security/group.xml',
        'security/record_rule.xml',
        'security/document_rule.xml',
        'views/res_users.xml',
        'views/stock_picking.xml',
        'views/stock_location.xml',
        'views/stock_quant.xml',
        'views/stock_warehouse.xml',
    ],
    'auto_install': False,
    'application': False,
}