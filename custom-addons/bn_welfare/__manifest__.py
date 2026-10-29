{
    'name': 'Welfare',
    'version': '17.0.1.5.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/Welfare',
    'depends': [
        'bn_microfinance',
        'bn_pos_cheque',
        'bn_direct_deposit',
        'bn_profile_management',
        'bn_analytic_account_customization',
        'bn_master_setup',
        'bn_res_company',
    ],
    'data': [
        'security/group.xml',
        'security/group_category.xml',
        'security/ir.model.access.csv',
        
        'data/sequence.xml',
        'data/hr_employee_category.xml',
        'data/server_action_fetch_welfare.xml',
        'data/ir_cron_auto_deliver.xml',
        'data/disbursement_category.xml',
        
        'reports/report_welfare_collection_document.xml',
        
        'views/welfare_institution_fetch_log.xml',
        'views/welfare.xml',
        'views/product_product.xml',
        'views/product_template.xml',
        'views/record_search.xml',
        'views/welfare_consolidated_line.xml',
        'views/disbursement_category.xml',
        'views/disbursement_application_type.xml',
        'views/welfare_limit_view.xml',
        'views/hr_employee.xml',
        'views/advance_donation.xml',
        
        'wizards/check_marfat_shift.xml',
        'wizards/wizard_view.xml',
        'data/bn_program_types.xml',
    ],
    'auto_install': False,
    'application': True,
    'assets': {
        'point_of_sale._assets_pos': [
            'bn_welfare/static/src/app/**/*',
            'bn_welfare/static/src/screens/**/*',
        ],
    }
} # type: ignore