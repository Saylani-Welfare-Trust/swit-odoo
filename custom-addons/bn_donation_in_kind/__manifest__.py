{
    'name': 'Donation In Kind',
    'version': '17.0.1.5.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Donation In Kind',
    'depends': [
        'bn_stock_location',
        'bn_import_donation',
        'bn_pos_custom_action',
        'bn_sms_whatsapp',
    ],
    'data': [
        'data/ir_module_category.xml',
        'security/group.xml',
        'security/ir.model.access.csv',
        'security/access_right.xml',
        'security/stock_scope_rule.xml',
        
        'data/data.xml',
        'data/sequence.xml',
        'data/server_action.xml',
        
        'reports/donation_in_kind_report.xml',
        'reports/donation_in_kind_transfer_report.xml',
        
        'views/donation_in_kind.xml',
        'views/res_partner.xml',
        'views/product_template.xml',
        'views/product_product.xml',
        'views/donation_in_kind_config.xml',
        'views/pos_menu.xml',
        'data/bn_program_types.xml',
    ],
    'auto_install': False,
    'application': True,
    'assets': {
        'point_of_sale._assets_pos': [
            'bn_donation_in_kind/static/src/app/**/*',
        ],
    },
}