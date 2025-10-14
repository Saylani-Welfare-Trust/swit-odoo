# -*- coding: utf-8 -*-
{
    'name': "Purchase Requisition Budget Management",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['employee_purchase_requisition','purchase_request', 'product'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'security/security_group.xml',
        'views/employee_purchase_requisition_budget.xml',
        'views/budget_department.xml',
        'views/stock_picking_pr.xml',
        'views/purchase_request_inherit.xml',
        'views/product_template.xml',
        'data/sequence.xml',
        'views/purchase_order_vendor.xml',
        'views/terms_reference.xml',
        'report/report.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
