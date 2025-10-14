{
    'name': 'Profile Management',
    'version': '1.0',
    'summary': 'Layer above Contacts',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Profile Management',
    'depends': [
        'base',
        'contacts',
        'base_accounting_kit',
        'hr',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner_layer.xml',
        'views/res_partner.xml',
        'views/action.xml',

        'views/product.xml',

        'views/menu.xml',

        'data/schedule_action.xml',

        'reports/microfinance_application_form.xml',
        'reports/welfare_application_form.xml',
        'reports/donee_form.xml',
    ],
    'auto_install': False,
    'application': True,
}