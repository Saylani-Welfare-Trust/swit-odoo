{
    'name': 'Planning',
    'version': '1.0',
    'author': 'Syed Owais Noor',
    'website': 'http://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/Planning',
    'depends': [
        'mail',
        'product',
        'bn_kitchen',
    ],
    'data': [
        'data/stock_location.xml',
        'security/ir.model.access.csv',
        'views/monthly_planning_views.xml',
        'views/planning_type_view.xml',
        'views/report_monthly_planning_line_views.xml',
        
        'wizard/import_monthly_planning_wizard_views.xml',
    ],
    'auto_install': False,
    'application': True,
}