{
    'name': 'POS Order Customizaiton',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/POS Order Customizaiton',
    'depends': [
        'point_of_sale'
    ],
    'data': [
        'data/paper_format.xml',
        'security/group.xml',
        'reports/duplicate_dn.xml',
        'views/pos_order.xml',
    ],
    'auto_install': False,
    'application': False,
}