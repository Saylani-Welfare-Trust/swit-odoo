{
    'name': 'Advance Donation',
    'version': '1.0',
    'description': "",
    'author': 'Muhammad Abdullah',
    'website': 'http://bytesnode.com',
    'category': 'BytesNode/Advance Donation',
    'depends': [
        'account',
        'point_of_sale',
        'bn_import_donation',
        'dynamic_accounts_report',
        # 'bn_master_setup',
    ],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',

        'data/sequences.xml',
        'data/sync_pos_donation_receipts_action.xml',
        'reports/advance_donation_report.xml',
        'reports/non_cash_advance_donation_report.xml',
        'reports/non_cash_disbursement_report.xml',
        'reports/report_advance_donation_receipt.xml',
        'wizard/partial_payment.xml',
        'views/advance_donation.xml',
        'views/donation_receipt.xml',
        'views/product_template.xml',
        'views/product_product.xml',
        'views/menu.xml',
        'views/advance_donation_gl.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'bn_advance_donation/static/src/js/advance_donation_gl.js',
        ],
        'point_of_sale._assets_pos': [
            'bn_advance_donation/static/src/app/**/*.js',
            'bn_advance_donation/static/src/app/**/*.xml',
        ],
    },
    'license': 'AGPL-3',
    'installable': True,
    'application': False
}