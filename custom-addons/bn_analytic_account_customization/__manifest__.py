{
    'name': 'Analytical Account Enhancement',
    'version': '17.0.1.1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Analytical Account Enhancement',
    'depends': [
        'hr_expense',
        'bn_master_setup',
        'account_analytic_parent',
    ],
    'data': [
        'security/group.xml',
        'security/ir.model.access.csv',
        'views/location_option.xml',
        'views/sub_zone.xml',
        'views/analytic_account.xml',
        'views/analytic_distribution_model.xml',
        'views/hr_employee.xml',
    ],
    'auto_install': False,
    'application': False,
}