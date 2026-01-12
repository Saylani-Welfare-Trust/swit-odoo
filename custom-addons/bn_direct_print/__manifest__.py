{
    'name': 'Direct Print',
    'version': '1.0',
    'description': '',
    'summary': 'Show the Print option against a report directly',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Direct Print',
    'depends': [
        'web'
    ],
    'data': [],
    'auto_install': False,
    'application': False,
    "assets": {
        "web.assets_backend": [
            # "bn_direct_print/static/lib/print.min.js",
            # "bn_direct_print/static/lib/print.min.css",
            "bn_direct_print/static/src/js/browser_print_dialog.js",
        ],
    },
}