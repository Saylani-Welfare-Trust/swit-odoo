# -*- coding: utf-8 -*-
{
    'name': 'Material Request',
    'version': '1.0',
    'category': 'BytesNode/Material Request',
    'summary': 'Internal Transfer Request with Budget Check and Multi-level Approval',
    'description': """
        This module provides a workflow for internal transfer requests with:
        - Budget checking functionality
        - HOD approval for in-budget requests
        - Committee (CFO + COO) approval for out-of-budget requests
        - Automatic internal transfer creation upon final approval
    """,
    'author': 'Muhammad Abdullah',
    'website': 'https://www.bytesnode.com',
    'depends': [
        'base',
        'stock',
        'base_account_budget',
        'mail',
        'purchase_requisition',
    ],
    'data': [
        'security/groups.xml',
        'security/record_rule.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/material_request_views.xml',
        'views/purchase_requisition_views.xml',
        'views/wizard_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
} # type: ignore
