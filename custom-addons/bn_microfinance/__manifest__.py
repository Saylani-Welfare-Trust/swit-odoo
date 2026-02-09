{
    'name': 'Microfinance',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Microfinance',
    'depends': [
        'bn_master_setup',
        'bn_profile_management',
        'bn_pos_order',
        'bn_advance_donation',
    ],
    'data': [
        'security/group.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/microfinance.xml',
        'views/microfinance_installment.xml',
        'views/product_product.xml',
        'views/product_template.xml',
        'views/res_partner.xml',
        'views/record_search.xml',
        'wizards/return_microfinance_product.xml',
        'reports/microfinance_pdc_template_report.xml',
        'reports/microfinance_receipt_report.xml',
        'reports/microfinance_security_deposit_report.xml',
        'reports/microfinance_installment_plan_report.xml',
        'reports/microfinance_approval_certificate_report.xml',
    ],
    'auto_install': False,
    'application': True,
    'assets': {
        'point_of_sale._assets_pos': [
            'bn_microfinance/static/src/app/**/*',
        ],
    }
} # type: ignore