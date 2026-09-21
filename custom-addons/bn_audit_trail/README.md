# Audit Trail (Odoo 17)

Generic audit trail module for Saylani Welfare and International Trust's
Odoo 17 instance. **Every standard and custom model is audited
automatically** for Create / Update / Delete / View, with field-level
**Before/After** values on updates, per user, per date. A small
configuration screen (**Audit Trail > Excluded Models**) lets you turn
off logging for specific models you've decided don't need a trail -
everything else stays audited with no setup.

## Install / upgrade

1. Copy the `bn_audit_trail` folder into your Odoo `addons` path
   (e.g. `/mnt/extra-addons/bn_audit_trail`).
2. Restart the Odoo service.
3. Apps > Update Apps List > search "Audit Trail" > Install (or
   Upgrade, if updating from an earlier version).

Nothing else is required to start auditing. Use Excluded Models only if
you actively want to turn a specific model off.

## How it works

- Inherits Odoo's `base` model, so `create()`, `write()`, `unlink()`
  and `_read_format()` (the internal method that classic `read()`,
  `web_read()` and `web_search_read()` all funnel through - this
  matters because Odoo 17's web client mostly uses the latter two, not
  classic `read()`) are wrapped for every model in the registry - no
  per-module code needed, standard or custom.
- **Default policy: audit everything.** A model is skipped only if:
  1. It's in the small, fixed, code-level list in
     `AUDIT_EXCLUDED_MODELS` (`models/base_override.py`) - internal
     Odoo plumbing (document numbering, cron, bus, mail bookkeeping,
     attachments, the audit tables themselves) that isn't meant to be
     end-user configurable, or
  2. It's been added to **Audit Trail > Excluded Models**
     (`audit.trail.exclusion`) - the configuration screen for turning
     off a specific model you've decided isn't worth logging.
- The exclusion list is cached in memory for performance, and - unlike
  an earlier version of this module - **the cache is correctly cleared**
  every time you add, edit, or remove an exclusion, so changes apply
  immediately with no restart. (The earlier bug was calling
  `env.registry.clear_caches()`, which did not reliably invalidate
  anything; this version uses `self.clear_caches()`, the documented,
  stable Odoo API for clearing a model's own cached methods.)

## Usage

1. Install/upgrade - Create/Update/Delete/View are logged for every
   model already, no setup step.
2. Go to **Audit Trail > Logs** to see the trail: filter/group-by user,
   model, action, date. Click into any `Update` entry and open the
   **"Field Changes (Before / After)"** tab to see exactly which fields
   changed, with the old and new value side by side for each one.
3. To audit a specific user's activity end to end: filter/search by
   that user in Logs, then Group By > Model or > Date to see everything
   they created, changed, deleted, and viewed.
4. To stop logging a specific model: **Audit Trail > Excluded Models** >
   add a line > pick the model > optionally note why. It stops being
   logged (Create/Update/Delete/View, all of it) as soon as you save -
   no restart, no upgrade needed.

## Access control

Two dedicated groups are created (nothing is exposed to normal users
by default):

- **Audit Trail / Viewer** - can browse the log (read-only), cannot
  see or change Excluded Models.
- **Audit Trail / Manager** - can browse the log, delete old entries,
  and manage Excluded Models. The default Administrator user is added
  to this group automatically.

Assign these from **Settings > Users > (user) > Access Rights**, under
the "Administration" category. If you can't see the Audit Trail menu
at all, this is the first thing to check - only `base.user_admin`
(the literal seed Administrator account) is auto-added; any other
admin/owner account needs to be added manually.

## Performance & volume

- `unlink` (delete) logging is cheap - just a display name snapshot,
  no diff.
- `write` logging computes a per-field Before/After diff - the main
  cost, negligible for normal business usage.
- `View` (read) logging is the highest-volume type by far, since it
  applies to every model by default. Duplicate reads of the same
  record by the same user within one request are deduplicated
  automatically, and the internal "before value" fetch that update
  logging needs no longer generates a spurious View entry as a
  side-effect (fixed in this version) - but expect View entries to
  still be the largest share of the log table by a wide margin.
- If a specific model turns out too noisy in practice - a detail-line
  model rewritten constantly, a background sync hitting one model hard
  - add it to **Excluded Models**. That's now the intended, working way
  to do it.
- Deliberately NOT excluded by default: core financial and inventory
  line models (e.g. `account.move.line`, `stock.move.line`). Given
  this is a donor-funded NGO, that trail is very likely something you
  want kept - add it to Excluded Models yourself if experience after
  go-live shows otherwise.
- `audit.trail.log` will grow indefinitely by design. Plan a periodic
  archiving/export policy (export + purge logs older than N months)
  once you see real volume after go-live.
