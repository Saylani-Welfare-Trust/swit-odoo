{
    'name': "MicroFinance Loan",
    'category': 'BytesNode/MicroFinance',

    'author': "Abul Hassan Khan Ghauri",
    'support': 'ahassankg@gmail.com',
    "website": "https://bytesnode.com/",

    # 'depends': ['stock', 'account', 'base', 'sm_point_of_sale_apps', 'report_xlsx'],
    # 'depends': ['bn_profile_management', 'stock', 'sm_point_of_sale_apps', 'report_xlsx'],
    'depends': ['bn_profile_management', 'bn_profile_search', 'stock', 'report_xlsx'],

    'data': [
        'views/loan_report.xml',
        'views/recover_product_widget.xml',
        'views/mfd_loan_request.xml',
        'views/mfd_bank.xml',
        'views/mfd_account_configuration.xml',
        'views/mfd_installment_receipt.xml',
        # 'views/mfd_loan_customer.xml',
        'views/pdc_cheque.xml',
        'views/mfd_scheme.xml',
        'views/mfd_recovery.xml',
        'views/confirm_search.xml',
        'views/search_record.xml',
        'views/menu.xml',

        'views/res_partner.xml',

        'reports/installment_receipt_template.xml',
        'reports/mfd_sd_slip_template.xml',
        'reports/mfd_slip_template.xml',
        'reports/report.xml',


        'data/sequences.xml',
        'data/configuration.xml',
        'data/res_group.xml',
        'data/cron_job.xml',
        'security/ir.model.access.csv'
    ],
    'auto_install': False,
    'application': True,
}