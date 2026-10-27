{
    'name': 'Medical Equipment',
    'version': '17.0.1.1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Medical Equipment',
    'depends': [
        'bn_profile_management',
        'bn_pos_custom_action',
        'bn_pos_cheque',
        'bn_donation_box',
        'bn_master_setup',
        'bn_res_company',
        'stock',
        'product',
    ],
    'data': [
        
        'security/group.xml',
        'security/access_right.xml',
        'security/ir.model.access.csv',
        
        'data/sequence.xml',
        'data/stock_location.xml',
        'data/stock_picking_type.xml',
        
        'views/product_template.xml',
        'views/product_product.xml',
        'views/medical_equipment.xml',
        'views/medical_equipment_reference.xml',
        'views/medical_security_deposit.xml',
        'views/res_partner.xml',
        'views/medical_equipment_category.xml',
        
        'wizards/medical_equipment_donation.xml',
    ],
    'auto_install': False,
    'application': True,
    'assets': {
        'point_of_sale._assets_pos': [
            'bn_medical_equipment/static/src/app/**/*',
            'bn_medical_equipment/static/src/screens/**/*',
        ],
    },
}