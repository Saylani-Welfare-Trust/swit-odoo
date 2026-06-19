{
    'name': 'Donation In Kind',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Donation In Kind',
    'depends': [
        'bn_import_donation'
    ],
    'data': [
        'data/sequence.xml',
        'security/group.xml',
        'security/ir.model.access.csv',
        'views/donation_in_kind.xml',
        'views/res_partner.xml',
    ],
    'auto_install': False,
    'application': False,
}