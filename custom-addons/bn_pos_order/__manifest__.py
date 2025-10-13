{
    'name': 'POS Order',
    'version': '1.0.0',
    'summary': 'Customizations for POS orders and receipts',
    'description': 'This module provides enhancements for POS orders and their receipts.',
    'author': 'Abdullah',
    'website': 'https://bytesnode.com',
    'category': 'BytesNode',
    'depends': ['point_of_sale', 'cheques_account'],
    'data': [
        # Add your XML/CSV data files here, e.g.:
        'security/group.xml',
        'report/pos_donation_receipt_report.xml',
        'report/pos_donation_receipt_template.xml',
        'views/pos_order_actions.xml',
        'views/pos_order_tree_view.xml',
        'views/pos_config.xml',
        # 'views/pos_receipt_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}