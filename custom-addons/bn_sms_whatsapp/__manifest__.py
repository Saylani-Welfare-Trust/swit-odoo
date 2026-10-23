{
    'name': 'SMS & WhatsApp Integration',
    'version': '1.0',
    'author': 'Labeeb Farooq',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/SMS & WhatsApp Integration',
    'depends': [
        'base',
        'bn_profile_management',
        'bn_pos_order',
        'bn_pos_customization',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [  
            'bn_sms_whatsapp/static/src/js/payment_screen.js',
        ],
    },
    'auto_install': False,
    'application': False,
}