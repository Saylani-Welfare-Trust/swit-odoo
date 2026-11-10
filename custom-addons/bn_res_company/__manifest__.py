{
    'name': 'Company Customization (Attachment Size Limit)',
    'version': '17.0.1.2.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/Company Customization',
    'depends': [
        'base',
        'mail',
    ],
    'data': [
        'views/res_company.xml',
    ],
    "assets": {
        "web.assets_backend": [
            "bn_res_company/static/src/js/chatter.js",
        ],
    },
    'auto_install': False,
    'application': False,
}