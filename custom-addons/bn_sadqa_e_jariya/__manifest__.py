{
    'name': 'Sadqa e Jariya',
    'version': '1.0',
    'author': 'BytesNode',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Sadqa e Jariya',
    'depends': [
        'bn_welfare',
        'bn_profile_management',
        'bn_res_company',
    ],
    'data': [
        'security/group.xml',
        'security/ir.model.access.csv',

        'data/sequence.xml',
        'data/server_action_fetch_welfare.xml',

        'views/welfare.xml',
        'views/welfare_institution_fetch_log.xml',
        'views/menu.xml',

        'wizards/wizard_view.xml',
    ],
    'auto_install': False,
    'application': True,
} # type: ignore
