{
    'name': 'Medical Equipment',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Medical Equipment',
    'depends': [
        'bn_profile_management',
        'bn_pos_custom_action'
    ],
    'data': [
        'security/group.xml',
        'security/access_right.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/stock_location.xml',
        'data/stock_picking_type.xml',
        'views/medical_equipment.xml',
        'views/medical_security_deposit.xml',
        'views/product_product.xml',
        'views/product_template.xml',
        'views/res_partner.xml',
        'views/medical_equipment_category.xml',
        'wizards/medical_equipment_donation.xml',
    ],
    'auto_install': False,
    'application': True,
    'assets': {
        'point_of_sale._assets_pos': [
            'bn_medical_equipment/static/src/app/**/*',
        ],
    },
}