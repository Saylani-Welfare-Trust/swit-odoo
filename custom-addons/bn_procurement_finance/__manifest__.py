{
    'name': 'Procurement Finance & Treasury',
    'version': '1.0',
    'author': 'BytesNode',
    'website': 'http://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/Purchase Customization',
    'summary': 'Finance confirmation and Treasury forwarding gate for vendor bills, '
               'before payment can be registered',
    'depends': [
        'account',
        'purchase',
    ],
    'data': [
        'security/group.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
