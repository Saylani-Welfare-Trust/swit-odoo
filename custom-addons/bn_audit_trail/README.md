# Audit Trail (Odoo 17)

Generic audit trail module for Saylani Welfare and International Trust's
Odoo 17 instance. Logs Create / Update / Delete activity on **any** model -
built-in (Contacts, Sales, Accounting, Inventory, HR, etc.) or custom -
with field-level before/after values.

## Install

1. Copy the `audit_trail` folder into your Odoo `addons` path
   (e.g. `/mnt/extra-addons/audit_trail`).
2. Restart the Odoo service.
3. Apps > Update Apps List > search "Audit Trail" > Install.

## How it works

- Inherits Odoo's `base` model, so `create()`, `write()` and `unlink()`
  are wrapped for every model in the registry - no per-module code needed.
- A rule table (`audit.trail.rule`) decides which models are actually
  logged and for which operations, so nothing is tracked until you turn
  it on. This keeps normal traffic fast and keeps the log free of noise.
- Rules are cached in memory (`ormcache`) and the cache is cleared
  automatically whenever you add/edit/remove a rule - changes apply
  immediately, no restart required.
- A fixed exclusion list (`AUDIT_EXCLUDED_MODELS` in
  `models/base_override.py`) keeps the audit log's own tables, cron,
  bus, mail tracking, etc. out of scope to avoid recursion and noise.

## Usage

1. As an Administrator, go to **Audit Trail > Configuration > Audit Rules**.
2. Click "Add a model to start auditing it".
3. Pick a model (e.g. `res.partner`, `sale.order`, or any custom model),
   choose which of Create / Update / Delete to track, save.
4. Go to **Audit Trail > Logs** to see the trail, with filters/group-by
   for user, model, action, and date. Click into a log to see the
   exact field-by-field before/after values for an update.

## Access control

Two dedicated groups are created (nothing is exposed to normal users
by default):

- **Audit Trail / Viewer** - can browse the log, cannot change rules.
- **Audit Trail / Manager** - can configure rules and browse the log.
  The default Administrator user is added to this group automatically.

Assign these from **Settings > Users > (user) > Access Rights**, under
the "Administration" category.

## Notes / recommendations for a large instance like Saylani's

- Don't enable auditing on every model at once - start with the
  financially/operationally sensitive ones (donations/CRM, accounting
  entries, inventory adjustments, HR/payroll, user & access changes)
  and expand from there.
- `unlink` (delete) logging is cheap - always safe to enable everywhere
  that matters, since it just needs a display name, not a full diff.
- `write` logging captures a diff per field, so high-frequency models
  (e.g. something updated on every page view) should be audited
  selectively, only for the fields/models that actually matter.
- Consider a periodic archiving/export job for `audit.trail.log` once
  volume grows, since this table will grow indefinitely by design.
