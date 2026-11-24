{
    'name': 'POS Cheque',
    'version': '17.0.1.4.7',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/POS Cheque',
    'depends': ['bn_stock_location', 
        'account',
        'bn_closing_session',
        'bn_pos_custom_action',
        'bn_pos_order',
        'bn_sms_whatsapp',
    ],
    'data': [
        'security/group.xml',
        'security/ir.model.access.csv', 'security/analytic_scope_rule.xml',
        
        'reports/pos_order_receipt.xml',
        'reports/donation_note.xml',
        
        'views/pos_cheque.xml',
        'views/pos_order.xml',
        'views/res_config_settings.xml',

        'data/res_company.xml',
        'views/pos_link_views.xml',
        'views/search_views.xml',
        'views/search_filters.xml',
        'views/chatter_forms.xml',
        'views/node_views.xml',
        'security/node_rules.xml',
    ],
    'auto_install': False,
    'application': False,
    'assets': {
        'point_of_sale._assets_pos': [
            'bn_pos_cheque/static/src/app/**/*',
            'bn_pos_cheque/static/src/screens/**/*',
            'bn_pos_cheque/static/src/models/*',
        ],
    }
}