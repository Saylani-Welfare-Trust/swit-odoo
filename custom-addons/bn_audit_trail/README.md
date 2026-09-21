# Audit Trail (Odoo 17)

Generic audit trail module for Saylani Welfare and International Trust's
Odoo 17 instance. **Every standard and custom model is audited by
default** for Create / Update / Delete, with field-level before/after
values, per user, per date. View/Read tracking (who opened/looked at a
record) is available but stays opt-in per model given its volume.

## Install

1. Copy the `bn_audit_trail` folder into your Odoo `addons` path
   (e.g. `/mnt/extra-addons/bn_audit_trail`).
2. Restart the Odoo service.
3. Apps > Update Apps List > search "Audit Trail" > Install.

Nothing else is required - as soon as it's installed, every model in
the system is being audited for Create/Update/Delete.

## How it works

- Inherits Odoo's `base` model, so `create()`, `write()`, `unlink()`
  (and `read()`, for View tracking) are wrapped for every model in the
  registry - no per-module code needed, standard or custom.
- **Default policy: audit everything.** Create/Update/Delete are logged
  for every model unless you say otherwise. You don't add a row to
  configure a model "in" - it already is.
- **Audit Exceptions** (`audit.trail.rule`) is where you configure the
  exceptions to that default:
  - Untick Create/Update/Delete for a specific model to turn that
    operation OFF for it (typically a high-volume, low business-value
    model you don't want filling up the log).
  - Tick "Log View (Read)" for a specific model to turn View tracking
    ON for it - View stays off everywhere else regardless.
- A small fixed list (`AUDIT_EXCLUDED_MODELS` in
  `models/base_override.py`) is hardcoded off no matter what - this is
  purely internal Odoo machinery (the audit log's own tables, cron,
  bus, mail notifications/tracking, attachments) where logging would
  either recurse on itself or be pure noise. This is not meant to be
  edited from the UI; if you want one of these turned on, that's a code
  change, ask me.

## Usage

1. Install the module - Create/Update/Delete are now being logged for
   every model in the system already.
2. Go to **Audit Trail > Logs** to see the trail, with filters/group-by
   for user, model, action, and date. Click into a log to see the
   exact field-by-field before/after values for an update.
3. To audit a specific user's activity end to end: open **Audit Trail >
   Logs**, filter/search by that user, then Group By > Model or > Date
   to see everything they created, changed, deleted, and (if enabled)
   viewed.
4. Only go to **Audit Trail > Configuration > Audit Exceptions** if you
   want to:
   - silence a specific noisy/low-value model (untick an operation), or
   - switch on View/Read tracking for a specific sensitive model.

### View (read) tracking - still opt-in

"View" logs every time a user's session actually loads a record's field
data - this is what tells you *who read which record*. It stays **off
by default** even though everything else is now on, because it's by far
the highest-volume log type. To turn it on for a model: Audit
Exceptions > add the model > tick "Log View (Read)".

Technical note: this is hooked at `_read_format()`, the internal method
that Odoo 17's `read()`, `web_read()` and `web_search_read()` all funnel
through - not just the classic `read()` method. This matters because
the modern web client mostly uses `web_read`/`web_search_read`, which
do NOT go through classic `read()`; hooking only `read()` would silently
miss most real browser activity. The trade-off: `_read_format()` also
fires for some internal/indirect access (e.g. a related record's name
being pulled in to display on another form), not only explicit "user
opened this record's own form" events - the per-transaction dedup below
keeps that from turning into log spam, but expect the count to include
some incidental access, not only direct opens.

Duplicate reads of the same record by the same user within one request
are deduplicated automatically, so opening one form doesn't produce a
dozen near-identical rows. Still, recommended: enable it only on
genuinely sensitive models - donor/beneficiary records, payroll, HR
files - not across the board.

## Access control

Two dedicated groups are created (nothing is exposed to normal users
by default):

- **Audit Trail / Viewer** - can browse the log, cannot change exceptions.
- **Audit Trail / Manager** - can manage exceptions and browse the log.
  The default Administrator user is added to this group automatically.

Assign these from **Settings > Users > (user) > Access Rights**, under
the "Administration" category.

## Cache note

`audit.trail.rule` exceptions are cached in memory for performance. This
version does not auto-clear that cache when you add/edit/remove an
exception (that call was removed to resolve an earlier install issue).
Practical effect: after changing an exception, do one of the following
for it to take effect:
- restart the Odoo service, or
- Apps > update the Audit Trail module (Upgrade), which reloads the
  registry and clears the cache as a side effect.

This only affects exceptions. It does not affect the default policy
itself (everything audited) - that's decided in code, not cached data.

## Performance & volume - what to expect with everything on by default

This is the trade-off of "audit everything, configure the exceptions":
volume and a small amount of overhead on every write, across the whole
system, all the time - not just on the models you care most about.

- `unlink` (delete) logging is cheap - just a display name snapshot,
  no diff - fine to leave on everywhere.
- `write` logging computes a per-field diff, so it's the main cost.
  For most business models this is negligible. Consider adding an
  exception (untick Log Update) for any model you notice is both very
  high-frequency AND not something you actually need write-level
  history for - candidates to watch after go-live: detail/line models
  that get rewritten constantly during recalculation (e.g. certain
  stock or accounting line models), and any custom model driving a
  tight automation loop.
- Deliberately NOT pre-excluded: core financial and inventory line
  models (e.g. `account.move.line`, `stock.move.line`). Given this is
  a donor-funded NGO, I've left these under the default "audited"
  policy rather than guessing they're noise - you may well want that
  trail. Add an exception for them yourself if experience shows
  otherwise.
- `audit.trail.log` will grow indefinitely by design. Plan a periodic
  archiving/export policy (e.g. export + purge logs older than N
  months) once you see real volume after go-live.
