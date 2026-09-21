# Audit Trail (Odoo 17)

Generic audit trail module for Saylani Welfare and International Trust's
Odoo 17 instance. **Every standard and custom model is audited
automatically** for Create / Update / Delete / View, with field-level
before/after values, per user, per date. **There is no configuration
screen** - it just works the moment it's installed.

(An earlier version had a database-backed "Audit Exceptions" config
screen to opt models in/out. It was removed: its rule cache didn't
auto-refresh, so toggling a setting there silently didn't take effect
until a restart, which made it look broken. The fixed exclusion list
below replaces it with something that can't go stale.)

## Install

1. Copy the `bn_audit_trail` folder into your Odoo `addons` path
   (e.g. `/mnt/extra-addons/bn_audit_trail`).
2. Restart the Odoo service.
3. Apps > Update Apps List > search "Audit Trail" > Install (or
   Upgrade, if updating from an earlier version of this module).

Nothing else is required. As soon as it's installed, every model in
the system - Create, Update, Delete, and View - is being audited.

If you're upgrading from the earlier version that had the "Audit
Exceptions" screen: that model and menu are gone. Any exception rows
you'd previously configured no longer apply - everything is now
audited uniformly per the policy below.

## How it works

- Inherits Odoo's `base` model, so `create()`, `write()`, `unlink()`
  and `_read_format()` (the internal method that classic `read()`,
  `web_read()` and `web_search_read()` all funnel through) are wrapped
  for every model in the registry - no per-module code needed,
  standard or custom.
- **Policy: audit everything.** There is no on/off switch to configure
  per model.
- A small, fixed, **code-level** exclusion list
  (`AUDIT_EXCLUDED_MODELS` in `models/base_override.py`) is the only
  exception. It's hardcoded on purpose - not a database setting - so
  there's nothing that can silently misconfigure or go stale. It
  currently excludes:
  - The audit log's own tables (would recurse on itself).
  - `ir.cron`, `ir.cron.trigger`, `ir.logging`, `bus.bus`,
    `bus.presence`, `ir.attachment` - internal machinery, not business
    data.
  - `mail.message`, `mail.notification`, `mail.tracking.value`,
    `mail.followers`, `mail.activity` - Odoo's own messaging/tracking
    bookkeeping, not the actual business record.
  - `ir.sequence`, `ir.sequence.date_range` - document numbering
    counters; these get written on literally every invoice/SO/etc.
    created system-wide and would flood the log with no audit value.
  - `ir.model.data`, `ir.default` - internal bookkeeping.
- To exclude another model (e.g. you discover a specific high-volume
  detail-line model isn't worth logging), that's a one-line code
  change to that set - ask me and I'll add it and redeploy. This is
  deliberately not a runtime setting, precisely because the runtime
  version of this was the source of the earlier bugs.

## Usage

1. Install/upgrade the module - Create/Update/Delete/View are now
   being logged for every model in the system already, no setup step.
2. Go to **Audit Trail** (top-level menu) to see the trail, with
   filters/group-by for user, model, action, and date. Click into a
   log to see the exact field-by-field before/after values for an
   update.
3. To audit a specific user's activity end to end: filter/search by
   that user in Audit Trail, then Group By > Model or > Date to see
   everything they created, changed, deleted, and viewed.

## Access control

Two dedicated groups are created (nothing is exposed to normal users
by default):

- **Audit Trail / Viewer** - can browse the log (read-only).
- **Audit Trail / Manager** - can browse the log and delete old
  entries (e.g. for archiving). The default Administrator user is
  added to this group automatically.

Assign these from **Settings > Users > (user) > Access Rights**, under
the "Administration" category. If you can't see the Audit Trail menu
at all, this is the first thing to check - only `base.user_admin`
(the literal seed Administrator account) is auto-added; any other
admin/owner account needs to be added manually.

## Performance & volume - what to expect with everything on

This is the trade-off of "audit everything, no configuration":
volume, across the whole system, all the time.

- `unlink` (delete) logging is cheap - just a display name snapshot,
  no diff.
- `write` logging computes a per-field diff - the main CPU/storage
  cost, but negligible for normal business usage.
- `View` (read) logging is the highest-volume type by a wide margin,
  and - now that there's no per-model opt-in - it applies everywhere.
  Duplicate reads of the same record by the same user within one
  request are deduplicated automatically (so opening one form doesn't
  produce a dozen rows), but expect this to be, by far, the largest
  share of the `audit.trail.log` table.
- Deliberately NOT excluded: core financial and inventory line models
  (e.g. `account.move.line`, `stock.move.line`). Given this is a
  donor-funded NGO, that trail is very likely something you want kept
  - if it turns out to be too noisy in practice, tell me and I'll add
  it to the exclusion list.
- `audit.trail.log` will grow indefinitely by design, and View logging
  makes that faster than before. Plan a periodic archiving/export
  policy (e.g. export + purge logs older than N months) once you see
  real volume after go-live - this is worth doing sooner rather than
  later given View is now unconditional.
