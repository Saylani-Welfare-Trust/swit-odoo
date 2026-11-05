# -*- coding: utf-8 -*-
{
    'name': 'Report Payment Cheque',
    'version': '1.0',
    'summary': 'Module holding custom cheque report',
    'author': 'Muhammad Abdullah',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Custom Reports',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'report/paper_formats.xml',
        'report/cheque_templates.xml',
        'views/bank_cheque_config_view.xml',
        'views/account_payment_view.xml',
    ],
    'installable': True,
    'application': False,
}
