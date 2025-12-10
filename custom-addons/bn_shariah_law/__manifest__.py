{
    'name': 'Shariah Law',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Shariah Law',
    'depends': [
        'bn_analytic_account_customization'
    ],
    'data': [
        'data/schedule_action.xml',
        'security/group.xml',
        'security/ir.model.access.csv',
        'views/shariah_law.xml',
        'views/pos_order.xml',
    ],
    'auto_install': False,
    'application': True,
}