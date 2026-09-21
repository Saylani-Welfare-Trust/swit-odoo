{
    'name': 'Audit Trail',
    'version': '17.0.1.0.0',
    'category': 'BytesNode/Audit Trail',
    'summary': 'Track create, update and delete activity across all Odoo models (standard & custom)',
    'description': """
Audit Trail
===========
Monitor and log Create / Update / Delete activity on any Odoo model
(built-in or custom), with field-level before/after values, per user,
per date, with configurable rules per model.

Key features
------------
* Enable/disable auditing per model, from a simple config screen
  (Audit Trail > Configuration > Audit Rules) - no code changes needed
  to start auditing a new custom model.
* Choose exactly which operations to track per model: Create, Update, Delete.
* Field-level before/after change tracking on updates (human-readable
  values for many2one, selection, boolean fields, etc).
* Full log viewer with filters and group-by (user, model, action, date).
* Access restricted to two dedicated security groups
  (Audit Trail Viewer / Audit Trail Manager) - normal users never see it.
* Built as a generic hook on the 'base' model, so it works for ANY
  installed module's models (Sales, Inventory, Accounting, custom apps...)
  without needing per-module code.
""",
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com',
    'license': 'LGPL-3',
    'depends': ['base'],
    'data': [
        'security/audit_security.xml',
        'security/ir.model.access.csv',
        'views/audit_rule_views.xml',
        'views/audit_log_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
