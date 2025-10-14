# -*- coding: utf-8 -*-
{
    'name': 'Donation Home Service',
    'version': '1.0',
    "category": "BytesNode/Donation Home Service",
    'author': 'ABUL HASSAN KHAN GHAURI',
    'website': 'https://bytesnode.com/',
    'depends': ['sm_point_of_sale_apps', 'stock'],
    'data': [
        'report/donation_home_service_template.xml',
        'report/report.xml',
        
        'views/donation_home_service.xml',
        'views/account_configuration.xml',
        'views/product_configuration.xml',
        'views/stock_picking.xml',
        'views/menu.xml',
        
        'data/sequences.xml',
        'data/configuration.xml',

        'security/ir.model.access.csv',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'ah_donation_home_service/static/src/js/*.js',
            'ah_donation_home_service/static/src/xml/*.xml',
        ],
    },
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False
}
