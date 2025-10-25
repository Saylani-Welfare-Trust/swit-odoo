{
    'name': 'Donation Box',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Donation Box',
    'depends': [
        'mail',
        'stock',
        'product',
        'bn_analytic_account_customization',
        'bn_master_setup_backup',
        'bn_pos_custom_action'
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/groups.xml',
        'data/sequence.xml',
        'data/stock_location.xml',
        'data/stock_picking_type.xml',
        'data/hr_employee_category.xml',
        'views/donation_box_request.xml',
        'views/donation_box_registration_intallation.xml',
        'views/donation_box_complain_center.xml',
        'views/product_product.xml',
        'views/product_template.xml',
        'views/stock_lot.xml',
        'reports/donation_box_report.xml',
    ],
    'auto_install': False,
    'application': True,
    'assets': {
        'point_of_sale._assets_pos': [
            'bn_donation_box/static/src/app/**/*',
        ],
    },
}