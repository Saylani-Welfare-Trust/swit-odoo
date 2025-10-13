{
    'name': 'Medical Equipment',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Medical Equipment',
    'depends': [
        'stock',
        'point_of_sale'
    ],
    'data': [
        'data/sequence.xml',
        'data/stock_location.xml',
        'data/stock_picking_type.xml',
        'security/group.xml',
        'security/ir.model.access.csv',
        'reports/medical_equipment_report.xml',
        'views/medical_equipment.xml',
        'views/product_product.xml',
        'views/product_template.xml',
    ],
    'auto_install': False,
    'application': False,
}