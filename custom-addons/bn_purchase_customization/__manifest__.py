{
    'name': 'Purchase Customization',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'http://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/Purchase Customization',
    'depends': [
        'purchase_requisition',
        'bn_master_setup',
    ],
    'data': [
        'security/group.xml',
        
        'data/sequence.xml',
        
        'views/purchase_requisition.xml',
        'views/purchase_requisition_type.xml',
        'views/purchase_order.xml',
    ],
    'auto_install': False,
    'application': False,
}