{
    'name': 'Analytical Account Enhancement',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Analytical Account Enhancement',
    'depends': [
        'hr_expense',
        'analytic',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/analytic_account.xml',
        'views/analytic_distribution_model.xml',
        'views/hr_employee.xml',
        'views/sub_zone.xml',
        'views/location_option.xml',
    ],
    'auto_install': False,
    'application': False,
}