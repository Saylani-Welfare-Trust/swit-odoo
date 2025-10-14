# -*- coding: utf-8 -*-
{
    'name': 'POS Closing Entry',

    "category": "BytesNode/POS Closing Entry",

    'author': 'ABUL HASSAN KHAN GHAURI',

    'depends': ['point_of_sale'],

    'data': [
        'views/pos_payment_method_view.xml',
        'views/pos_session_view.xml'
    ],

    'assets': {
        'point_of_sale._assets_pos': [
            'ah_pos_closing_entry/static/src/**/*.js',
            'ah_pos_closing_entry/static/src/**/*.xml',
        ],
    },

    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False
}
