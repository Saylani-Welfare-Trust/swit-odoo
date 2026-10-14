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
        'security/ir.model.access.csv',
        
        'data/stock_location.xml',
        'data/ir_cron.xml',
        
        'views/monthly_planning_views.xml',
        'views/planning_type_view.xml',
        'views/report_monthly_planning_line_views.xml',
        
        'wizard/import_monthly_planning_wizard_views.xml',
        'wizard/purchase_request_wizard.xml',
    ],
    'auto_install': False,
    'application': True,
}