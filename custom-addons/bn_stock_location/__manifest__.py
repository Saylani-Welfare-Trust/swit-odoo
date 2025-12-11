{
    'name': 'Stock Location Customization',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': '',
    'license': 'LGPL-3',
    'category': 'BytesNode/Stock Location Customization',
    'depends': [
        'stock',
        'bn_analytic_account_customization'
    ],
    'data': [
        'security/group.xml',
        'security/record_rule.xml',
        'views/res_users.xml',
        'views/stock_picking.xml',
        'views/stock_location.xml',
    ],
    'auto_install': False,
    'application': False,
}