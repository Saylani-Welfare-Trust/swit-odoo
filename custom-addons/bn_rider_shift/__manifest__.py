{
    'name': 'Rider Shift',
    'version': '1.0',
    'summary': 'Create Rider Shifts',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Rider Shift',
    'depends': [
        'mail',
        'bn_key_management',
        'sm_donation_box',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/groups.xml',
        'views/rider_shift.xml',
        'views/rider_collection.xml',
        'wizards/rider_shift.xml'
    ],
    'auto_install': False,
    'application': True,
}