{
    'name': 'Company Customization',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Company Customization',
    'depends': [
        'base'
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