{
    'name': 'Medical & Health',
    'version': '1.0',
    'summary': 'Medical & Health POS counters: patients (registered donees tagged Medical) are the customers',
    'author': 'BytesNode',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Medical & Health',
    'depends': [
        'bn_profile_management',
        'point_of_sale',
    ],
    'data': [
        'security/group.xml',
        'security/ir.model.access.csv',

        'wizards/patient_register_wizard.xml',

        'views/pos_config.xml',
        'views/pos_actions.xml',
        'views/patient.xml',
        'views/menu.xml',
    ],
    'uninstall_hook': '_uninstall_hook',
    'auto_install': False,
    'application': True,
    'assets': {
        'point_of_sale._assets_pos': [
            'bn_medical_pos/static/src/app/**/*',
        ],
    },
}
