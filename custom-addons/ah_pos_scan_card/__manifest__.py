# -*- coding: utf-8 -*-
{
    'name': 'POS Scan Card',

    'author': 'ABUL HASSAN KHAN GHAURI',

    'depends': ['point_of_sale', 'sm_point_of_sale_apps'],

    'data': [
        # 'views/pos_payment_method_view.xml',
        # 'views/pos_session_view.xml'
    ],

    'assets': {
        'point_of_sale._assets_pos': [
            'ah_pos_scan_card/static/src/**/*.js',
            'ah_pos_scan_card/static/src/**/*.xml',
        ],
    },

    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False
}
