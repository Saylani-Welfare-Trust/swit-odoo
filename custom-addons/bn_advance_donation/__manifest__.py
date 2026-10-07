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
        'reports/advance_donation_statement_report.xml',
        'wizard/partial_payment.xml',
        'views/advance_donation.xml',
        'views/donation_receipt.xml',
        'views/product_template.xml',
        'views/product_product.xml',
        'views/menu.xml',
        'views/advance_donation_statement_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'bn_advance_donation/static/src/js/advance_donation_statement.js',
            'bn_advance_donation/static/src/xml/advance_donation_statement.xml',
            'bn_advance_donation/static/src/js/x2many_selectable.js',
            'bn_advance_donation/static/src/xml/x2many_selectable.xml',
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