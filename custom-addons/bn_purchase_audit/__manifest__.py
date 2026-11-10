{
    'name': 'Purchase Audit',
    'version': '1.0',
    'author': 'BytesNode',
    'website': 'http://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/Purchase Customization',
    'summary': 'Purchase / Audit group: read-only access to the whole Purchase app, '
               'except its Configuration',
    'depends': [
        'purchase_requisition',
        'purchase_stock',
        'bn_purchase_customization',
        'bn_procurement_finance',
    ],
    'data': [
        'security/group.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',

        'views/menu.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
