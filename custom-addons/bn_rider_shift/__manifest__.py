{
    'name': 'Rider Shift',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Rider Shift',
    'depends': [
        'mail',
        'bn_key_management',
        'bn_donation_box',
    ],
    'data': [
        'data/sequence.xml',
        'security/ir.model.access.csv',
        'security/groups.xml',
        'views/rider_shift.xml',
        'views/rider_collection.xml',
        'views/counterfeit_notes.xml',
        'wizards/rider_schedule.xml'
    ],
    'auto_install': False,
    'application': False,
}