{
    'name': 'Audit Trail',
    'version': '17.0.2.5.0',
    'category': 'BytesNode/Audit Trail',
    'summary': 'Track create, update, view and delete activity across all Odoo models by default (standard & custom)',
    'description': """
Audit Trail
===========
Logs Create / Update / Delete / View activity on every Odoo model
(standard or custom), with field-level before/after values, per user,
per date.

Key features
------------
* Audits Create, Update, Delete and View on every model out of the box.
* Structured trail: each operation is a master entry, with everything it
  read or changed in other records listed under it as sub-operations.
* Field-level Before/After values on updates. Passwords, 2FA secrets,
  API keys and tokens are masked.
* Audit Trail > Excluded Models turns a specific model off; removing an
  exclusion is logged.
* Deleting log entries always leaves a purge entry.
* Groups: Access Root Menu, User (own activity), Audit (all, read-only),
  Manager (+ Excluded Models), Admin (+ purge).
""",
    'author': 'Syed Owais Noor',
    'website': 'https://bytesnode.com',
    'license': 'LGPL-3',
    'depends': ['base', 'web'],
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
