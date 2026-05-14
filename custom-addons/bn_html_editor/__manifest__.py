{
    'name': 'TinyMCE HTML Edit',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/TinyMCE HTML Edit',
    'depends': [
        'web',
        'bn_qurbani'
    ],
    'data': [
        'views/qurbani_order.xml'
    ],
    'auto_install': False,
    'application': False,
    "assets": {
        "web.assets_backend": [
            # TinyMCE library (LOCAL)
            "tinymce_odoo17/static/src/lib/tinymce/tinymce.min.js",

            # OWL JS field
            "tinymce_odoo17/static/src/js/tinymce_field.js",

            # XML template
            "tinymce_odoo17/static/src/xml/tinymce_field.xml",
        ],
    },
}