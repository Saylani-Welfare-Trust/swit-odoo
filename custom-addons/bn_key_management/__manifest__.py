{
    'name': 'Key Management',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Key Management',
    'depends': [
        'bn_donation_box'
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/groups.xml',
        'data/schedule_action.xml',
        'wizards/bulk_key_issuance.xml',
        'wizards/manual_key_issuance.xml',
        'views/key.xml',
        'views/key_bunch.xml',
        'views/key_issuance.xml',
        'views/donation_box_request.xml',
        'views/donation_box_registration_installation.xml'
    ],
    'auto_install': False,
    'application': False,
}