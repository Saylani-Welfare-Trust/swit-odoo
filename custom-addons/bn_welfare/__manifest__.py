{
    'name': 'Welfare',
    'version': '1.0',
    'summary': 'Welfare App',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Welfare',
    'depends': [
        'mail',
        'bn_profile_management',
        'bn_profile_search',
        'point_of_sale',
        'account',
        'product',
        'bn_master_setups'
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence.xml',

        'reports/disbursement_slip.xml',
        
        'views/account_configuration.xml',
        'views/disbursement_category.xml',
        'views/disbursement_type.xml',
        'views/disbursement_request.xml',
        # 'views/search_record.xml',
        # 'views/confirm_search.xml',
        'views/res_partner.xml',
        'views/disbursement_bank.xml',
        'views/welfare.xml',
    ],
    'auto_install': False,
    'application': True,
    'assets': {
        'point_of_sale._assets_pos': [
            'bn_welfare/static/src/xml/disbursementPopup.xml',
            'bn_welfare/static/src/js/disbursementPopup.js',
        ],
    },
}