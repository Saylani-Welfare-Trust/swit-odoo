{
    'name': 'Donation Home Service',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Donation Home Service',
    'depends': [
        'stock',
        'product',
        'bn_pos_custom_action',
        'bn_import_donation',
    ],
    'data': [
        'security/group.xml',
        'security/access_right.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/stock_location.xml',
        'data/stock_picking_type.xml',
        'views/donation_home_service.xml',
        'views/product_template.xml',
        'views/product_product.xml',
        'reports/donation_home_service_report.xml',
    ],
    'auto_install': False,
    'application': False,
    'assets': {
        'point_of_sale._assets_pos': [
            'bn_donation_home_service/static/src/app/**/*',
            'bn_donation_home_service/static/src/screens/*',
        ],
    },
}