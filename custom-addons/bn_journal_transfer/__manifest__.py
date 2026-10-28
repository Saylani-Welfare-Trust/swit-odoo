{
    'name': 'Journal Transfer',
    'version': '17.0.1.1.0',
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
        
        'views/journal_transfer.xml'
    ],
    'auto_install': False,
    'application': False,
}