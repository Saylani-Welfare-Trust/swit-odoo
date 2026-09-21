{
    'name': 'Audit Trail',
    'version': '17.0.2.1.0',
    'category': 'BytesNode/Audit Trail',
    'summary': 'Track create, update, view and delete activity across all Odoo models by default (standard & custom)',
    'description': """
Audit Trail
===========
Monitor and log Create / Update / Delete / View activity across EVERY
Odoo model (built-in or custom) by default, with field-level before/after
values, per user, per date. Audits everything out of the box - use the
Excluded Models screen only for the specific models you've decided
aren't worth logging.

Key features
------------
* Audits Create, Update, Delete AND View (who read/opened which record)
  on every standard and custom model out of the box - no setup required
  to get a working trail.
* Audit Trail > Excluded Models lets you turn a specific model off
  entirely (no more Create/Update/Delete/View logs for it) - e.g. a
  very high-frequency technical/detail model you've decided isn't
  worth logging. Takes effect immediately, no restart needed.
* A small fixed, code-level list additionally excludes internal Odoo
  plumbing (document numbering, cron, bus, mail bookkeeping,
  attachments) that would otherwise be pure noise - not user-editable,
  by design.
* Field-level Before/After change tracking on updates (human-readable
  values for many2one, selection, boolean fields, etc), viewable on
  each Update log entry's "Field Changes" tab.
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
        'views/audit_exclusion_views.xml',
        'views/audit_log_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
