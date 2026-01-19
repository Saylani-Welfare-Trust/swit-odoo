{
    'name': 'POS Custom Button',
    'version': '1.0',
    'author': 'Syd Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/POS Custom Button',
    'depends': [
        'point_of_sale'
    ],
    'data': [
        'views/pos_order.xml',
        # 'views/res_company.xml',
    ],
    'auto_install': False,
    'application': False,
    'assets': {
        'point_of_sale._assets_pos': [
            'bn_pos_custom_action/static/src/app/action_button/action_button.js',
            'bn_pos_custom_action/static/src/app/action_button/action_button.xml',
            'bn_pos_custom_action/static/src/app/action_screen/action_screen.js',
            'bn_pos_custom_action/static/src/app/action_screen/action_screen.xml',
            'bn_pos_custom_action/static/src/app/provisional_popup/provisional_popup.js',
            'bn_pos_custom_action/static/src/app/provisional_popup/provisional_popup.xml',
            'bn_pos_custom_action/static/src/app/receiving_popup/receiving_popup.js',
            'bn_pos_custom_action/static/src/app/receiving_popup/receiving_popup.xml',
            'bn_pos_custom_action/static/src/screens/**/*',
            'bn_pos_custom_action/static/src/override/app/**/*',
            'bn_pos_custom_action/static/src/models/*',
        ],
    },
} # type: ignore