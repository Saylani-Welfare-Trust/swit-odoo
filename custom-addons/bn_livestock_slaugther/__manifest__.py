{
    'name': 'Livestock Slaugther',
    'version': '17.0.1.5.0',
    'author': 'Syed Owais Noor',
    'website': 'http://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/Livestock Slaugther',
    'depends': [
        'bn_stock_location',
        'bn_donation_home_service',
        'bn_pos_cheque',
        'bn_direct_deposit',
        'bn_import_donation',
        'mrp',
        'mail',
        'purchase_requisition',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/stock_scope_rule.xml',
        
        'data/sequence.xml',
        'data/stock_location.xml',
        
        'reports/livestock_bulk_transfer_report.xml',
        
        'views/livestock_slaugther.xml',
        'views/livestock_requisition.xml',
        'views/livestock_cutting.xml',
        'views/livestock_cutting_material.xml',
        'views/product_packaging.xml',
        'views/package_type.xml',
        'views/meat_management.xml',
        'views/distribution_center.xml',
        
        'wizards/livestock_slaugther.xml',
        'data/bn_program_types.xml',
    ],
    'auto_install': False,
    'application': True,
}