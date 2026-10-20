{
    'name': 'Journal Transfer',
    'version': '1.1',
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