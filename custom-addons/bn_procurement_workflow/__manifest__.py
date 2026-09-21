{
    'name': 'Procurement Workflow',
    'version': '1.0',
    'author': 'BytesNode',
    'website': 'http://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/Purchase Customization',
    'summary': 'Procurement Manager review, RFQ, Technical Evaluation, HOD Procurement '
               'and Funds Availability gates on top of Purchase Requisitions',
    'depends': [
        'purchase_requisition',
        'bn_purchase_customization',
        'bn_material_request',
        'bn_shariah_law',
    ],
    'data': [
        'security/group.xml',
        'security/ir.model.access.csv',
        'views/procurement_defer_wizard_views.xml',
        'views/arrange_budget_wizard_views.xml',
        'views/purchase_requisition_views.xml',
        'views/material_request_views.xml',
        'views/purchase_order_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
