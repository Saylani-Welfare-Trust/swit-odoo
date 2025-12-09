{
    'name': 'Direct Deposit',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Direct Deposit',
    'depends': [
        'bn_pos_cheque'
    ],
    'data': [
        'data/sequence.xml',
        'security/ir.model.access.csv',
        'views/direct_deposit.xml',
    ],
    'auto_install': False,
    'application': False,
    'assets': {
        'point_of_sale._assets_pos': [
            'bn_direct_deposit/static/src/app/**/*',
        ],
    },
}