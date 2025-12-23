{
    'name': 'Direct Deposit',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Direct Deposit',
    'depends': [
        'bn_pos_cheque',
        'bn_donation_home_service',
    
    ],
    'data': [
        'data/sequence.xml',
        'security/ir.model.access.csv',
        'views/direct_deposit.xml',
        'reports/direct_deposit_provisional_report.xml',
        'reports/direct_deposit_duplicate_report.xml',

    ],
    'auto_install': False,
    'application': False,
    'assets': {
        'point_of_sale._assets_pos': [
            'bn_direct_deposit/static/src/app/**/*',
        ],
    },
} # type: ignore