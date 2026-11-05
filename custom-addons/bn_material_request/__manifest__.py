# -*- coding: utf-8 -*-
{
    'name': 'Material Request',
    'version': '17.0.1.3.0',
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
    'website': 'https://bytesnode.com',
    'depends': [
        'base',
        'stock',
        'base_account_budget',
        'mail',
        'purchase_requisition',
        'bn_stock_location',
        # The multi-PR / multi-page vendor-selection wizard filters other Purchase
        # Requests by the "Procurement Manager Approval" state, which this module
        # defines (PURCHASE_REQUISITION_STATES).
        'bn_purchase_customization',
    ],
    'data': [
        'security/groups.xml',
        'security/record_rule.xml',
        'security/ir.model.access.csv',
        'security/stock_scope_rule.xml',
        'data/sequence.xml',
        'data/state_cleanup.xml',
        
        'views/material_request_views.xml',
        'views/purchase_requisition_views.xml',
        'views/purchase_requisition_line_deletion_log_views.xml',
        'views/wizard_views.xml',
        'views/purchase_order.xml',
        'views/stock_picking_views.xml',
        'data/bn_program_types.xml',
        'wizards/material_request_revert_wizard_views.xml',
        'views/bn_search_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
} # type: ignore

