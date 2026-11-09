{
    'name': 'Sadqa e Jariya',
    'version': '2.3',
    'author': 'BytesNode',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Sadqa e Jariya',
    'summary': 'Institution disbursement (masjid and madrasa) with its own portal, approvals and payout',
    'depends': [
        'account',
        'stock',
        'hr',
        'point_of_sale',
        'base_accounting_kit',
        'bn_master_setup',
        'bn_profile_management',
        'bn_res_company',
        'bn_sms_whatsapp',
        'bn_pos_custom_action',
        'bn_pos_order',
    ],
    'data': [
        'security/group.xml',
        'security/ir.model.access.csv',

        'data/sequence.xml',
        'data/data.xml',
        'data/ir_cron.xml',
        'data/server_action_fetch.xml',
        'data/mail_template.xml',

        'reports/collection_report.xml',
        'reports/donee_profile_report.xml',

        'views/sadqa_jariya.xml',
        'views/sadqa_jariya_line.xml',
        'views/sadqa_jariya_fetch_log.xml',
        'views/configuration.xml',
        'views/res_company.xml',

        'wizards/wizard_views.xml',
        'wizards/record_search_views.xml',

        'views/menu.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'bn_sadqa_e_jariya/static/src/pos/**/*',
        ],
    },
    'auto_install': False,
    'application': True,
} # type: ignore
