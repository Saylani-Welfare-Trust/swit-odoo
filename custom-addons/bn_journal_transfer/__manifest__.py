{
    'name': 'Journal Transfer',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'http://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/Journal Transfer',
    'depends': [
        'bn_pos_cheque'
    ],
    'data': [
        'data/sequence.xml',
        'data/schedule_action.xml',
        'security/group.xml',
        'security/ir.model.access.csv',
        'views/journal_transfer.xml'
    ],
    'auto_install': False,
    'application': False,
}