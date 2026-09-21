{
    'name': 'Audit Trail',
    'version': '17.0.1.1.0',
    'category': 'BytesNode/Audit Trail',
    'summary': 'Track create, update, view and delete activity across all Odoo models by default (standard & custom)',
    'description': """
Audit Trail
===========
Monitor and log Create / Update / Delete / View activity across EVERY
Odoo model (built-in or custom) by default, with field-level before/after
values, per user, per date. Nothing to configure to get started - add
exceptions only where you want to turn something off (or turn View
tracking on).

Key features
------------
* Audits Create, Update and Delete on every standard and custom model
  out of the box - no per-model setup required.
* Audit Exceptions screen (Audit Trail > Configuration) lets you turn
  OFF specific operations for specific (usually high-volume, low-value)
  models, and turn ON View/Read tracking (who opened/read a record),
  which stays opt-in only given its volume.
* Field-level before/after change tracking on updates (human-readable
  values for many2one, selection, boolean fields, etc).
* Full log viewer with filters and group-by (user, model, action, date) -
  filter by user to see everything one person created, changed, deleted
  and viewed.
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
