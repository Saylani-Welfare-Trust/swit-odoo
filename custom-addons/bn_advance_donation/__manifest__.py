{
    'name': 'Advance Donation',
    'version': '1.0',
    'description': "",
    'author': 'Muhammad Abdullah',
    'website': 'http://bytesnode.com',
    'category': 'BytesNode/Advance Donation',
    'depends': [
        'account',
        'bn_import_donation',
        # 'bn_master_setup',
    ],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',

        'data/sequences.xml',
        'reports/advance_donation_report.xml',
        'reports/non_cash_advance_donation_report.xml',
        'views/advance_donation.xml',
        'views/donation_receipt.xml',
        'views/product_template.xml',
        'views/product_product.xml',
        'views/menu.xml',
    ],
    # 'assets': {
    #     'point_of_sale._assets_pos': [
    #         'bn_advance_donation/static/src/**/*.js',
    #         'bn_advance_donation/static/src/**/*.xml',
    #     ],
    # },
    'license': 'AGPL-3',
    'installable': True,
    'application': False
} # type: ignore
