{
    'name': 'Payment Customization',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/Payment Customization',
    'depends': [
        'account'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/account_payment.xml',
        'data/ibft_sequence.xml',
        'wizard/ibft_wizard.xml',

    ],
    'auto_install': False,
    'application': False,
}