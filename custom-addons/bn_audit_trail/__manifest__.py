{
    'name': 'Audit Trail',
    'version': '17.0.2.0.0',
    'category': 'BytesNode/Audit Trail',
    'summary': 'Track create, update, view and delete activity across all Odoo models by default (standard & custom)',
    'description': """
Audit Trail
===========
Monitor and log Create / Update / Delete / View activity across EVERY
Odoo model (built-in or custom) by default, with field-level before/after
values, per user, per date. Zero configuration - there is no settings
screen and nothing to turn on; it just works for every model as soon as
it's installed.

Key features
------------
* Audits Create, Update, Delete AND View (who read/opened which record)
  on every standard and custom model out of the box - no setup, no
  per-model configuration screen.
* A small fixed, code-level list excludes only internal Odoo plumbing
  (document numbering, cron, bus, mail bookkeeping, attachments) that
  would otherwise be pure noise - not a runtime setting, so there's
  nothing that can silently go stale or misconfigure.
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
        'views/audit_log_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
