{
    'name': 'Qurbani',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'http://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/Qurbani',
    'depends': [
        'product',
        'stock',
        'bn_donation_home_service',
        'point_of_sale'
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/qurbani_day_data.xml',
        'views/qurbani_schedule.xml',
        'views/qurbani_order.xml',
        'views/qurbani_day.xml',
        'reports/qurbani_token.xml',
    ],
    'auto_install': False,
    'application': True,
    # 'assets': {
    #     'point_of_sale._assets_pos': [
    #         'bn_qurbani/static/src/screens/**/*',
    #     ],
    # }
}