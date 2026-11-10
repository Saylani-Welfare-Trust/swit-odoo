{
    'name': 'Inventory Customization',
    'version': '17.0.1.2.0',
    'author': 'Syed Owais Noor',
    'website': 'http://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/Inventory Customization',
    'depends': [
        'bn_master_setup',
        'base',
        'product',
        'stock',
        'stock_account',
        'purchase',
        'purchase_stock',
        'analytic',
        'bn_shariah_law',
        'bn_donation_home_service',
    ],
    'data': [
        'data/absorb.xml',
        'security/stock_security.xml',
        'security/ir.model.access.csv',
        
        'data/demo_data.xml',
        
        'reports/purchase_order_report.xml',
        
        'views/livestock_variant.xml',
        'views/product_attribute_value.xml',
        'views/product_template.xml',
        'views/product_product.xml',
        'views/purchase_order.xml',
        'views/stock_picking.xml',
        'views/stock_move.xml',
        
        'wizards/receive_by_weight.xml',
        'wizards/receipt_reason_wizard.xml',
        'views/search_views.xml',
    ],
    'auto_install': False,
    'application': False,
}