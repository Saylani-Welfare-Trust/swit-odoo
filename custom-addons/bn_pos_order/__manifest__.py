{
    'name': 'POS Order Customizaiton',
    'version': '17.0.1.1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/POS Order Customizaiton',
    'depends': [
        'bn_pos_customization',
        'bn_profile_management',
        'bn_pos_custom_action',
    ],
    'data': [
        'security/group.xml',
        
        'data/paper_format.xml',
        'data/server_action.xml',
        
        'reports/whatsapp_dn.xml',
        'reports/duplicate_dn.xml',
        
        'views/pos_order.xml',
        'views/res_partner.xml',
    ],
    'auto_install': False,
    'application': False,
}