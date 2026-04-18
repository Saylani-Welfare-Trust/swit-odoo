{
    'name': 'Qurbani',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'http://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/Qurbani',
    'depends': [
        'bn_stock_location',
        'bn_donation_home_service',
        'bn_pos_customization',
    ],
    'data': [
        'data/sequence.xml',
        'data/chand_raat.xml',
        'data/qurbani_day.xml',
        'security/ir.model.access.csv',
        'views/qurbani_day.xml',
        'views/hijri.xml',
        'views/chand_raat.xml',
        'views/city_schedule.xml',
        'views/slaughter_schedule.xml',
        'views/distribution_schedule.xml',
        'views/qurbani_order.xml',
        'wizards/qurbani_schedule.xml',
        'reports/qurbani_token.xml',
    ],
    'auto_install': False,
    'application': True,
    # 'assets': {
    #     'point_of_sale._assets_pos': [
    #         'bn_qurbani/static/src/app/**/*',
    #         'bn_qurbani/static/src/screens/**/*',
    #         'bn_qurbani/static/src/components/**/*',
    #         'bn_qurbani/static/src/models/*',
    #     ],
    # }
}