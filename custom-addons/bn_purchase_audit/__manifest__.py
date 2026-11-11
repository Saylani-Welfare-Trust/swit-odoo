{
    'name': 'Purchase Audit',
    'version': '1.1',
    'author': 'BytesNode',
    'website': 'http://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/Purchase Customization',
    'summary': 'Purchase / Audit group: read-only access to the whole Purchase app '
               '(except its Configuration), to all Material Requests, and to the '
               'Vendors menu of Accounting',
    'depends': [
        'purchase_requisition',
        'purchase_stock',
        'bn_purchase_customization',
        'bn_procurement_finance',
        'bn_material_request',
    ],
    'data': [
        'security/group.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',

        'views/menu.xml',
        'views/purchase_order_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
