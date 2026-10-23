{
    'name': 'Import Donation',
    'version': '17.0.1.2.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Import Donation',
    'depends': [
        'stock',
        'product',
        'base_accounting_kit',
        'bn_profile_management',
    ],
    'external_dependencies': {
        'python': ['openpyxl', 'xlrd'],
    },
    'data': [
        'data/sequence.xml',
        'data/schedule_action.xml',
        'data/server_action.xml',
        'data/ir_module_category.xml',
        'data/stock_location.xml',
        'data/stock_picking_type.xml',

        'security/group.xml',
        'security/ir.model.access.csv',
        
        'reports/import_donation.xml',
        'reports/api_donation.xml',

        'views/import_donation.xml',
        'views/donation.xml',
        'wizards/api_donaiton_wizard.xml',
        'views/api_donation.xml',
        'views/fetch_history.xml',
        'views/fetch_log.xml',
        'views/res_partner.xml',
        'views/product_template.xml',
        'views/product_product.xml',
        'views/header_type.xml',
        'views/gateway_config.xml',
        'views/res_company.xml',

        'data/upgrade_hooks.xml',
    ],
    'auto_install': False,
    'application': True,
}
