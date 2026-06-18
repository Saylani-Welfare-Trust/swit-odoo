{
    'name': 'Import Donation',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Import Donation',
    'depends': [
        'stock',
        'product',
        'base_account_budget',
        'bn_profile_management',
    ],
    'data': [
        'data/sequence.xml',
        'data/ir_module_category.xml',
        
        'security/group.xml',
        'security/access_right.xml',
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
    ],
    'auto_install': False,
    'application': True,
} # type: ignore