# -*- coding: utf-8 -*-
{
    'name': "live_stock_slaughter",

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
    'depends': ['base', 'stock', 'product', 'mrp'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'kitchen/kitchen_transfer.xml',
        'mrp/mrp_inherit.xml',

        'views/raw_meat_requirement.xml',
        'views/livestock_stock.xml',
        'views/livestock_branch_request.xml',
        'views/cutting_dept.xml',
        'views/meat_dept.xml',
        'views/goat_dept.xml',
        'views/cutting.xml',
        'views/meat_requisition.xml',
        'views/livestock_requisition.xml',
        'views/by_products_master.xml',
        'views/views.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}

