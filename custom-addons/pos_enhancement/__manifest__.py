# -*- coding: utf-8 -*-
{
    'name': "POS Enhancements",
    "version": "1.0",
    "summary": "Customize POS ",
    "category": "BytesNode/Sales/Point of Sale",
    "author": "Muhammad Mudasir ",
    "website": "https://bytesnode.com/",
    "license": "LGPL-3",
    "depends": ['bn_profile_management','stock', 'customization_pos'],
    "data": [
        "security/groups.xml",
        "security/ir.model.access.csv",
        "views/ir_sequence.xml",
        # "views/res_partner_form.xml",
        "views/registered_order_tree.xml",
        "views/registered_order_form.xml",
        "views/handle_register_order_form.xml",
        "views/product_template_form.xml",
        "views/menu.xml",
        "views/pos_order.xml",
        # "views/schedule_action.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "assets": {
        'point_of_sale._assets_pos': [
            'pos_enhancement/static/src/**/*',
    ]}
}
