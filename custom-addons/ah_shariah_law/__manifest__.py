# -*- coding: utf-8 -*-
{
    'name': 'AH Shariah Compliance',
    'version': '1.0',
    'description': "",
    'author': 'ABUL HASSAN KHAN GHAURI',
    'website': '',
    'depends': ['bn_profile_management', 'account'],
    'data': [
        'data/groups.xml',
        'data/configuration.xml',

        'security/ir.model.access.csv',

        'views/shariah_law.xml',
        'views/shariah_law_transfer_wizard.xml',
        'views/shariah_law_account_conf.xml',
        'views/res_partner.xml',
        'views/chart_of_account_conf.xml',
        'views/menu.xml',

    ],
    # 'assets': {
    #     'point_of_sale._assets_pos': [
    #         'ah_advance_donation/static/src/**/*.js',
    #         'ah_advance_donation/static/src/**/*.xml',
    #     ],
    # },
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': True
}
