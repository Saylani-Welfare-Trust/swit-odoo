{
    'name': 'Sadqa e Jariya',
    'version': '17.0.1.0.0',
    'author': 'BytesNode',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Sadqa e Jariya',
    'depends': [
        'bn_welfare',
        'bn_profile_management',
        'bn_master_setup',
        'bn_sms_whatsapp',
    ],
    'data': [
        'security/group.xml',
        'security/group_category.xml',
        'security/ir.model.access.csv',

        'data/sequence.xml',
        'data/server_action_fetch_welfare.xml',

        'views/welfare.xml',
        'views/welfare_institution_fetch_log.xml',
        'views/res_company.xml',
        'views/menu.xml',

        'wizards/wizard_view.xml',
    ],
    'auto_install': False,
    'application': True,
} # type: ignore
