{
    'name': "Enhanced POS Dashboard",
    'version': '17.0.2.0.1',
    'category': 'Point of Sale',
    'summary': """Detailed dashboard view for POS with advanced features""",
    'description': """
        Enhanced POS dashboard with:
        1. Top 5 products, customers, sales, peak hours tracking
        2. PDF report generation
        3. Multiple chart types (pie, polar area, line, donut, radar, bar)
        4. Detailed stats viewing
        5. Sales target setting
        6. Chart zoom functionality
        7. Advanced filters (Today, last week, last month, last year, custom date range)
        8. Editable dashboard data
        9. Currency: PKR
    """,
    'author': 'Abdul Hai',
    'company': 'BytesNode',
    'website': "https://www.bytesnode.com/",
    'depends': ['point_of_sale', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/pos_order_views.xml',
        'views/pos_sales_target_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'dashboard_pos/static/src/xml/pos_dashboard.xml',
            'dashboard_pos/static/src/js/pos_dashboard.js',
            'dashboard_pos/static/src/css/pos_dashboard.css',
            'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js',
            'https://cdn.jsdelivr.net/npm/chartjs-plugin-zoom@2.0.0/dist/chartjs-plugin-zoom.min.js',
        ],
    },
    'external_dependencies': {
        'python': ['pandas'],
    },
    'images': [
        'static/description/icon.png',
    ],
    'license': "AGPL-3",
    'installable': True,
    'application': False,
    'auto_install': False,
}