{
    'name': 'Rider Shift',
    'version': '17.0.1.1.0',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Rider Shift',
    'depends': [
        'bn_key_management',
        'bn_donation_box',
    ],
    'data': [
        'data/ir_module_category.xml',
        'data/sequence.xml',
        'security/groups.xml',
        'security/ir.model.access.csv',
        'views/rider_shift.xml',
        'views/rider_collection.xml',
        'views/counterfeit_notes.xml',
        'views/foreign_currency.xml',
        'wizards/rider_schedule.xml',
        'wizards/foreign_currency_wizard.xml',
        'wizards/counterfeit_notes_wizard.xml',
    ],
    'auto_install': False,
    'application': False,
    'assets': {
        'point_of_sale._assets_pos': [
            'bn_rider_shift/static/src/app/**/*',
        ],
    },
}