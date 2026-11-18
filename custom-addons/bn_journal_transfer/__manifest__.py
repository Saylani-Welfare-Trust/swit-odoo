{
    'name': 'Journal Transfer',
    'version': '17.0.1.2.0',
    'author': 'Syed Owais Noor',
    'website': 'http://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/Journal Transfer',
    'depends': [
        'bn_pos_cheque'
    ],
    'data': [
        'security/group.xml',
        'security/ir.model.access.csv',
        
        'data/sequence.xml',
        'data/schedule_action.xml',
        
        'views/journal_transfer.xml',

        'data/upgrade_hooks.xml',
        'views/pos_link_views.xml',
        'views/search_views.xml',
    ],
    'auto_install': False,
    'application': False,
}