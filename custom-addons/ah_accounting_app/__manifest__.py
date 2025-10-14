# -*- coding: utf-8 -*-
{
    'name': 'AH Accounting App',

    'author': 'ABUL HASSAN KHAN GHAURI',

    'depends': ['account', 'dynamic_accounts_report'],

    'data': [
        'views/account_analytic_plan.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ah_accounting_app/static/src/xml/profit_and_loss_template.xml',
            'ah_accounting_app/static/src/xml/balance_sheet_template.xml',
            # 'ah_accounting_app/static/src/xml/general_ledger_template.xml',

            'ah_accounting_app/static/src/js/profit_and_loss.js',
            'ah_accounting_app/static/src/js/balance_sheet.js',
            # 'ah_accounting_app/static/src/js/general_ledger.js',
        ],
    },
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False
}
