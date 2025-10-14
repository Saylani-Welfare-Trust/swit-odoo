# -*- coding: utf-8 -*-
{
    'name': 'Advance Donation',
    'version': '1.0',
    'description': "",
    'author': 'ABUL HASSAN KHAN GHAURI',
    'website': '',
    'depends': ['account', 'sm_config_bank', 'bn_import_donation', 'microfinance_loan'],
    'data': [
        'views/advance_donation.xml',
        'views/customer_reg.xml',
        'views/donation_receipt.xml',
        'views/category_conf.xml',
        'views/account_conf.xml',
        'views/menu.xml',

        'data/groups.xml',
        'data/account_conf.xml',
        'data/sequences.xml',

        'security/ir.model.access.csv',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'ah_advance_donation/static/src/**/*.js',
            'ah_advance_donation/static/src/**/*.xml',
        ],
    },
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False
}
