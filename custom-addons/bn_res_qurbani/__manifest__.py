# -*- coding: utf-8 -*-
{
    'name': 'Qurbani Company Extension',
    'version': '1.0',
    'summary': 'Inherit res.company and add custom field',
    'description': 'This module inherits res.company and adds one custom field.',
    'author': 'BytesNode',
    'category': 'Base',
    'depends': ['base', 'bn_pos_custom_action', 'bn_qurbani'],
    'data': [
        # Add XML view files here if needed
        'views/res_company_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}