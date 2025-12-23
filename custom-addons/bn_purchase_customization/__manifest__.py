{
    'name': 'Purchase Customization',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'http://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/Purchase Customization',
    'depends': [
        'purchase_requisition'
    ],
    'data': [
        'data/sequence.xml',
        'views/blanket_order.xml',
        'views/purchase_requisition_type.xml',
    ],
    'auto_install': False,
    'application': False,
}