{
    'name': 'Import Donation',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Import Donation',
    'depends': [
        'bn_profile_management'
    ],
    'data': [
        'data/sequence.xml',
        'security/group.xml',
        'security/ir.model.access.csv',
        'views/import_donation.xml',
        'views/donation.xml',
        'views/fetch_history.xml',
        'views/api_donation.xml',
        'views/res_partner.xml',
        'wizards/api_donaiton_wizard.xml',
    ],
    'auto_install': False,
    'application': True,
}
