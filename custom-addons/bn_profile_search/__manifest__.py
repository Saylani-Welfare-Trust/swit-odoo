{
    'name': 'Profile Search',
    'version': '1.0',
    'summary': 'Enable Profile Search in Microfinance, Welfare, Medical, and etc',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Profile Search',
    'depends': [
        'bn_profile_management'
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizards/confirm_search.xml',
        'wizards/search_record.xml',
        'views/search_menu.xml',
    ],
    'auto_install': False,
    'application': False,
}