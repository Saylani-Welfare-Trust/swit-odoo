{
    'name': 'Key Management',
    'version': '1.0',
    'summary': 'Key Management',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Key Management',
    'depends': [
        'sm_donation_box'
    ],
    'data': [
        # 'data/schedule_action.xml',
        
        'security/ir.model.access.csv',
        
        'wizards/bulk_key_issuance.xml',

        'views/key.xml',
        'views/key_issuance.xml',
        'views/key_location.xml',
        'views/donation_box_request.xml',
        'views/donation_box_registration.xml',
    ],
    'auto_install': False,
    'application': False,
}