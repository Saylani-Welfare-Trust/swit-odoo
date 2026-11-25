{
    'name': 'HR Expense Customization',
    'version': '17.0.1.2.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/HR Expense Customization',
    'depends': ['bn_stock_location', 
        'hr_expense',
        'bn_analytic_account_customization',
    ],
    'data': [
        'security/group.xml',
        'security/access_right.xml', 'security/analytic_scope_rule.xml',
        
        'views/hr_expense.xml',
        
        'report/report_paperformat.xml',
    ],
    'auto_install': False,
    'application': False,
}