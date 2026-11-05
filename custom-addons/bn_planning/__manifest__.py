{
    'name': 'Planning',
    'version': '17.0.1.3.0',
    'author': 'Syed Owais Noor',
    'website': 'http://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/Planning',
    'depends': [
        'bn_stock_location',
        'mail',
        'product',
        'bn_kitchen',
        'hr',
        'purchase_requisition',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/stock_scope_rule.xml',
        'security/planning_security.xml',
        
        'data/stock_location.xml',
        'data/ir_cron.xml',
        
        'views/monthly_planning_views.xml',
        'views/planning_type_view.xml',
        'views/report_monthly_planning_line_views.xml',
        
        'wizard/import_monthly_planning_wizard_views.xml',
        'wizard/purchase_request_wizard.xml',
        'data/program_types.xml',
        'views/search_views.xml',
    ],
    'auto_install': False,
    'application': True,
}