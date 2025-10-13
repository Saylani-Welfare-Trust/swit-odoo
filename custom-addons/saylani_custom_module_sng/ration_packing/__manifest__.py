# -*- coding: utf-8 -*-
{
    'name': "ration_packing",

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
    'depends': ['base', 'stock', 'product', 'mrp', 'point_of_sale', 'contacts', 'bn_welfare'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'inherit/contact_inherit.xml',
        'report/gate_pass.xml',
        'warehouse/warehouse_req.xml',
        'warehouse/kitchen_issue_req.xml',
        'welfare/donee_contract.xml',
        'welfare/welfare_daily_req.xml',
        'welfare/monthly_requirements.xml',
        'distribution_center/monthly_requirements.xml',
        'distribution_center/distribution_daily_req.xml',
        'views/ration_issuance_request.xml',
        'views/views.xml',
        'views/cron.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],

    'assets': {
        'point_of_sale.assets': [
            '/ration_packing/static/src/js/pos_nextday.js',
        ],

    },

}
