{
    'name': 'Microfinance',
    'version': '17.0.1.1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Microfinance',
    'depends': [
        'bn_master_setup',
        'bn_profile_management',
        'bn_pos_order',
        'bn_advance_donation',
        'bn_pos_custom_action',
        'sale_stock',
        'report_xlsx',
    ],
    'data': [
        'security/group.xml',
        'security/ir.model.access.csv',
        
        'data/sequence.xml',
        
        'reports/microfinance_pdc_template_report.xml',
        'reports/microfinance_receipt_report.xml',
        'reports/microfinance_security_deposit_report.xml',
        'reports/microfinance_installment_plan_report.xml',
        'reports/microfinance_approval_certificate_report.xml',
        
        'views/microfinance.xml',
        'views/microfinance_installment.xml',
        'views/product_product.xml',
        'views/product_template.xml',
        'views/res_partner.xml',
        'views/record_search.xml',
        'views/microfinance_pdc_consolidated_views.xml',
        'views/consolidate_installment_lines.xml',
        'views/microfinance_scheme.xml',
        'views/security_offered.xml',
        
        'wizards/return_microfinance_product.xml',
    ],
    'auto_install': False,
    'application': True,
    'assets': {
        'point_of_sale._assets_pos': [
            'bn_microfinance/static/src/app/**/*',
        ],
    }
} # type: ignore