{
    'name': 'POS Order Customizaiton',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/POS Order Customizaiton',
    'depends': [
        'point_of_sale',
        'bn_profile_management'
    ],
    'data': [
        'data/paper_format.xml',
        'security/group.xml',
        'views/pos_order.xml',
        'views/res_partner.xml',
        'reports/duplicate_dn.xml',
        'reports/whatsapp_dn.xml',
    ],
    'auto_install': False,
    'application': False,
}