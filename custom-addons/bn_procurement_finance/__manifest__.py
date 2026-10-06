{
    'name': 'Procurement Finance & Treasury',
    'version': '1.1',
    'author': 'BytesNode',
    'website': 'http://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/Purchase Customization',
    'summary': 'Finance confirmation and Treasury forwarding gate for vendor bills, '
               'before payment can be registered; draft vendor advance payments from '
               'Purchase Order Payment Terms',
    'depends': [
        'account',
        'purchase',
        # Its fields are used by the payment form view it overwrites
        # (account_check_printing.view_account_payment_form_inherited), so it has
        # to be loaded before this module extends that form.
        'base_accounting_kit',
    ],
    'data': [
        'security/group.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'data/payment_term_data.xml',
        'views/account_move_views.xml',
        'views/account_payment_term_views.xml',
        'views/account_payment_views.xml',
        'views/purchase_order_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
