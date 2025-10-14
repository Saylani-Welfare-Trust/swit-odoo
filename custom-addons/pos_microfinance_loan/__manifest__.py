# -*- coding: utf-8 -*-
{
    'name': 'POS Microfinance Loan',
    'version': '1.0',
    'description': "",
    'author': 'ABUL HASSAN KHAN GHAURI',
    'category': 'BytesNode/POS Microfinance Loan',
    'website': '',
    'depends': ['account', 'point_of_sale', 'microfinance_loan', 'customization_pos'],
    'data': [
        # 'security/ir.model.access.csv',
        # 'data/data.xml',
        # 'wizard/cash_import_wizard_views.xml',
        # 'views/cash_import.xml',
        # 'views/account_view.xml',
        # 'views/installment.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_microfinance_loan/static/src/js/*.js',
            'pos_microfinance_loan/static/src/xml/*.xml',
        ],
    },
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False
}
