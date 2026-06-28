{
    'name': 'Bank Reconciliation',
    'version': '1.0',
    'description': 'Bank Reconciliation Module for Odoo',
    'summary': 'Manage bank reconciliations',
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com',
    'license': 'LGPL-3',
    'category': 'BytesNode/Bank Reconciliation',
    'depends': [
        'base_accounting_kit'
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/bank_reconciliation_master.xml',
        'views/bank_reconciliation_transaction.xml',
        'views/bank_reconciliation_reconciled.xml',
        'views/menu.xml',
        'wizards/reconcile_wizard.xml',
        'wizards/import_bank_statement.xml',
    ],
    'auto_install': False,
    'application': True,
}