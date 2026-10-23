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
        'bn_inventory_customization',
        'bn_master_setup',
        
    ],
    'data': [
        'security/group.xml',
        'security/ir.model.access.csv',
        
        # 'data/mail_template_data.xml',
        
        'views/procurement_defer_wizard_views.xml',
        'views/arrange_budget_wizard_views.xml',
        'views/purchase_requisition_views.xml',
        'views/material_request_views.xml',
        'views/purchase_order_views.xml',
        'views/stock_picking_views.xml',
        'views/rfq_price_wizard_views.xml',
        'views/master_cxo_approver_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
