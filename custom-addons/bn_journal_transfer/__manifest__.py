{
    'name': 'Journal Transfer',
    'version': '17.0.1.2.9',
    'author': 'Syed Owais Noor',
    'website': 'http://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/Journal Transfer',
    'depends': ['bn_stock_location', 
        'bn_pos_cheque'
    ],
    'data': [
        'security/group.xml',
        'security/ir.model.access.csv', 'security/analytic_scope_rule.xml',
        
        'data/sequence.xml',
        'data/schedule_action.xml',
        
        'views/journal_transfer.xml',

        'data/upgrade_hooks.xml',
        'views/pos_link_views.xml',
        'views/search_views.xml',
        'views/search_filters.xml',
        'views/node_views.xml',
        'security/node_rules.xml',
    ],
    'auto_install': False,
    'application': False,
}