# -*- coding: utf-8 -*-
{
    'name': "kitchen_department",

    'summary': "Short (1 phrase/line) summary of the module's purpose",

    'description': """
Long description of module's purpose
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'product', 'mrp', 'purchase', 'stock', 'contacts','purchase_requisition', 'bn_welfare'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'report/gate_pass.xml',
        'views/product_category_inherit.xml',
        'views/kitchen_dailly_request.xml',
        'views/branch_shed.xml',
        'views/branch_requests.xml',
        'views/kitchen_material_requisition.xml',
        'views/views.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}

