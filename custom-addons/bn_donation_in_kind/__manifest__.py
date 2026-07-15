{
    'name': 'Donation In Kind',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Donation In Kind',
    'depends': [
        'bn_import_donation',
        'bn_pos_custom_action'
    ],
    'data': [
        'data/data.xml',
        'data/ir_module_category.xml',
        'data/sequence.xml',
        'data/server_action.xml',
        'security/group.xml',
        'security/ir.model.access.csv',
        'reports/donation_in_kind_report.xml',
        'views/donation_in_kind.xml',
        'views/res_partner.xml',
        'views/product_template.xml',
        'views/product_product.xml',
        'views/donation_in_kind_config.xml',
        'views/pos_menu.xml',
    ],
    'auto_install': False,
    'application': True,
    'assets': {
        'point_of_sale._assets_pos': [
            'bn_donation_in_kind/static/src/app/**/*',
        ],
    },
}