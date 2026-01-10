{
    'name': 'Welfare',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Welfare',
    'depends': [
        'bn_microfinance',
        'bn_profile_management',
        'bn_analytic_account_customization'
    ],
    'data': [
        'data/sequence.xml',
        'data/hr_employee_category.xml',
        'security/group.xml',
        'security/ir.model.access.csv',
        'views/welfare.xml',
        'views/product_product.xml',
        'views/product_template.xml',
        'views/record_search.xml',
    ],
    'auto_install': False,
    'application': True,
    'assets': {
        'point_of_sale._assets_pos': [
            'bn_welfare/static/src/app/**/*',
        ],
    }
}