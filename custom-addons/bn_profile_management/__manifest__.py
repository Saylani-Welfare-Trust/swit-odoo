{
    'name': 'Profile Management',
    'version': '1.1',
    'summary': 'Layer above Contacts',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Profile Management',
    'depends': [
        'bn_analytic_account_customization',
        'bn_pos_customization',
        # owns the company's Welfare API page (views/res_company.xml)
        'bn_res_company',
    ],
    'data': [
        'security/group.xml',
        'security/access_right.xml',
        'security/record_rule.xml',
        'security/ir.model.access.csv',
        
        'data/sequence.xml',
        'data/server_action.xml',
        'data/res_partner_category.xml',
        
        'reports/profile_management_report.xml',
        'reports/microfinance_report.xml',
        
        'views/res_partner.xml',
        'views/res_partner_layer.xml',
        'views/res_company.xml',
        
        'wizards/confirm_search.xml',
        'wizards/record_search.xml',
        'wizards/microfinance_application_wizard.xml',
    ],
    'auto_install': False,
    'application': True,
}