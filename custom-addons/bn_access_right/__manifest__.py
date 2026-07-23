{
    'name': 'Access Right',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Access Right',
    'depends': [
        'base',
        'mail',
        'hr',
        'contacts',
        'hr_expense',
        # 'spreadsheet_dashboard'
    ],
    'data': [
        'security/group.xml',
        'views/menu.xml',
        'views/chatter.xml'
    ],
    'auto_install': False,
    'application': True,
}