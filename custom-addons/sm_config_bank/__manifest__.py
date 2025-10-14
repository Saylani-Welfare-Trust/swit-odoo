{
    "name": "Custom Config Bank",
    "summary": """
       Custom Config Bank
    """,
    "description": """
        Custom Config Bank
    """,
    "category": "TechnoCoderSol/CustomConfigBank",
    "author": "Shariq Ali Mehdi",
    "version": "17.0",
    'license': 'OPL-1',
    'depends': ['base', 'account', 'analytic'],
    "data": [
        'security/ir.model.access.csv',
        # 'data/config_bank_data.xml',
        'views/config_bank_view.xml',
    ],
    "application": False,
    "installable": True,
    "auto_install": False,
}
