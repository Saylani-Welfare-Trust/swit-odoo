# -*- coding: utf-8 -*-
import logging
from contextlib import contextmanager

from odoo import api, models

from .audit_log import outer_hands_up

_logger = logging.getLogger(__name__)

# Every model is audited (Create, Update, Delete, View) by default. This
# fixed set is always excluded, no matter what - hardcoded, not
# database/UI-configured, so it can't be accidentally changed or go stale.
# These are internal Odoo plumbing models where logging would either
# recurse on itself (the audit log's own tables) or be high-volume,
# low-value noise (document numbering, cron, bus, mail bookkeeping,
# attachments). For excluding OTHER models via the UI, see
# audit.trail.exclusion (Audit Trail > Excluded Models).
#
# audit.trail.exclusion is NOT in this set: removing an exclusion is logged
# (see AUDIT_DELETE_ONLY_MODELS). Deleting audit.trail.log entries is traced
# separately (see AuditTrailLog.unlink).
#
# To add another permanent, code-level exclusion, add its technical name
# here and redeploy - this set is deliberately not meant to be end-user
# editable.
AUDIT_EXCLUDED_MODELS = {
    'audit.trail.log',
    'audit.trail.log.line',
    'ir.logging',
    'ir.cron',
    'ir.cron.trigger',
    'ir.attachment',
    'ir.sequence',
    'ir.sequence.date_range',
    'ir.model.data',
    'ir.default',
    'bus.bus',
    'bus.presence',
    'mail.message',
    'mail.notification',
    'mail.tracking.value',
    'mail.followers',
    'mail.activity',
}

# The Audit Trail's own configuration: only deletions are logged (removing
# an exclusion), never views, creations or updates. Purging log entries is
# traced separately (see AuditTrailLog.unlink).
AUDIT_DELETE_ONLY_MODELS = {
    'audit.trail.exclusion',
}


class Base(models.AbstractModel):
    """Inheriting 'base' patches EVERY model in the registry - built-in
    (res.partner, sale.order, account.move, ...) and custom alike - without
    needing to touch a single line of any other module.

    Policy: Create / Update / Delete / View are audited for every model
    by default, except:
      * AUDIT_EXCLUDED_MODELS above - fixed, code-level, not configurable.
      * Models listed in Audit Trail > Excluded Models (audit.trail.exclusion).

    Structure: every audited operation opens a "frame" for as long as it
    runs. Whatever else gets audited while that frame is open (a write on
    sale.order creating stock moves, a form opening reading the partner and
    company it shows, ...) is linked under the operation's own log entry as
    a sub-operation. See AuditTrailLog._audit_close_frame().

    Transaction safety: the log writes run inside their own non-flushing
    cursor SAVEPOINT via _audit_safe(). A failure in the logging code rolls
    back only that savepoint; the user's own operation and the rest of the
    request are unaffected. The savepoint must NOT flush: a flushing
    savepoint flushes the caller's pending writes *before* the savepoint
    exists, so a genuine error in those writes (e.g. a unique constraint)
    would be swallowed here and leave the transaction aborted, and it would
    also run the pre-commit hooks (chatter tracking ...) early.
    """
    _inherit = 'base'

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------
    def _audit_safe(self, func, *args, **kwargs):
        """Run func(*args, **kwargs) inside its own savepoint, swallowing
        (and logging) any exception - Python-level OR database-level -
        without ever letting it affect the caller's transaction."""
        try:
            with self.env.cr.savepoint(flush=False):
                return func(*args, **kwargs)
        except Exception:
            _logger.exception('Audit Trail: logging step failed for %s', self._name)
            return None

    def _audit_is_enabled(self):
        if self._transient or self._abstract:
            return False
        if self._name in AUDIT_EXCLUDED_MODELS:
            return False
        if not self.env.registry.ready:
            # Avoid touching our own tables while they're still being
            # created during this module's own installation.
            return False
        try:
            # Cached: no SQL once warm. The cache-miss query protects
            # itself with a savepoint (see audit.trail.exclusion).
            excluded = self.env['audit.trail.exclusion'].sudo()._get_excluded_model_names()
        except Exception:
            _logger.exception('Audit Trail: could not read the excluded models')
            excluded = set()
        return self._name not in excluded

    def _audit_logs_changes(self):
        """Create / Update / View logging (Delete uses _audit_is_enabled)."""
        return self._name not in AUDIT_DELETE_ONLY_MODELS and self._audit_is_enabled()

    def _audit_stack(self):
        """Open audit frames of the current transaction, innermost last."""
        transaction = self.env.transaction
        stack = getattr(transaction, '_audit_stack', None)
        if stack is None:
            stack = transaction._audit_stack = []
        return stack

    @contextmanager
    def _audit_frame(self, kind):
        """Group everything audited while the operation runs under the
        operation's own log entry. ``kind`` is 'read', 'create', 'write'
        or 'unlink'."""
        stack = self._audit_stack()
        frame = {'model': self._name, 'kind': kind, 'own': [], 'children': [], 'descendants': []}
        stack.append(frame)
        try:
            yield frame
        except Exception:
            stack.pop()
            # No SQL here: the transaction may be aborted. Hand the ids to
            # the enclosing frame so they are still linked if the error is
            # caught higher up.
            if stack:
                outer_hands_up(frame, stack[-1])
            raise
        stack.pop()
        outer = stack[-1] if stack else None
        if (frame['own'] and frame['children']) or (outer is None and frame['descendants']):
            # Linking needs SQL.
            self._audit_safe(self.env['audit.trail.log']._audit_close_frame, frame, outer)
        elif outer is not None:
            outer_hands_up(frame, outer)

    def _audit_register(self, logs, kind):
        """Attach freshly created log entries of this model to the innermost
        open frame: as the frame's own entries when they describe the
        operation itself, otherwise as entries it triggered."""
        stack = self._audit_stack()
        if not stack:
            return
        frame = stack[-1]
        if frame['model'] == self._name and frame['kind'] == kind:
            frame['own'] += logs.ids
        else:
            frame['children'] += logs.ids
            frame['descendants'] += logs.ids

    # -----------------------------------------------------------------
    # Create / Update / Delete
    # -----------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        if not self._audit_logs_changes():
            return super().create(vals_list)
        with self._audit_frame('create'):
            records = super().create(vals_list)
            if records:
                self._audit_safe(self.env['audit.trail.log']._log_create, records, vals_list)
        return records

    def write(self, vals):
        if not self._audit_logs_changes():
            return super().write(vals)
        with self._audit_frame('write'):
            def _snapshot():
                tracked = [f for f in vals.keys() if f in self._fields]
                # Fetch pre-write values for the diff without that internal
                # fetch itself generating a spurious View/read log entry.
                rs = self.with_context(_audit_trail_skip_read=True)
                return {rec.id: {f: rec[f] for f in tracked} for rec in rs}
            old_values = self._audit_safe(_snapshot) or {}

            result = super().write(vals)

            self._audit_safe(self.env['audit.trail.log']._log_write, self, vals, old_values)
        return result

    def unlink(self):
        if not self._audit_is_enabled():
            return super().unlink()
        with self._audit_frame('unlink'):
            def _snapshot():
                return {rec.id: self.env['audit.trail.log']._safe_display_name(rec)
                        for rec in self}
            snapshot = self._audit_safe(_snapshot) or {}

            result = super().unlink()

            if snapshot:
                self._audit_safe(self.env['audit.trail.log']._log_unlink, self._name, snapshot)
        return result

    # -----------------------------------------------------------------
    # View
    # -----------------------------------------------------------------
    def _audit_read_frame_enabled(self):
        return bool(self._ids) and not self.env.context.get('_audit_trail_skip_read') \
            and self._audit_logs_changes()

    def read(self, fields=None, load='_classic_read'):
        if not self._audit_read_frame_enabled():
            return super().read(fields=fields, load=load)
        with self._audit_frame('read'):
            return super().read(fields=fields, load=load)

    def web_read(self, specification):
        # Opening a form: the record itself is read first, then a nested
        # web_read() per linked record shown (partner, company, lines ...).
        # The frame puts those linked reads under the record's View entry.
        if not self._audit_read_frame_enabled():
            return super().web_read(specification)
        with self._audit_frame('read'):
            return super().web_read(specification)

    @api.model
    def web_search_read(self, domain, specification, offset=0, limit=None, order=None, count_limit=None):
        # @api.model is required: the web client calls this without record
        # ids, and call_kw() decides how to call it from the decorator.
        kwargs = dict(offset=offset, limit=limit, order=order, count_limit=count_limit)
        if not self._audit_logs_changes():
            return super().web_search_read(domain, specification, **kwargs)
        with self._audit_frame('read'):
            return super().web_search_read(domain, specification, **kwargs)

    def _read_format(self, fnames, load='_classic_read'):
        # Logged here rather than in read() - Odoo 17's web client mostly
        # calls web_read()/web_search_read(), not the classic read(); both
        # of those, and classic read() itself, all funnel through
        # _read_format() internally. Hooking this one method catches every
        # access path (browser UI, RPC, XML-RPC) uniformly.
        result = super()._read_format(fnames, load=load)
        if (self._ids and not self.env.context.get('_audit_trail_skip_read')
                and self._audit_logs_changes()):
            Log = self.env['audit.trail.log']
            rows = Log._unseen_read_rows(self._name, result)
            if rows:
                self._audit_safe(Log._log_read, self._name, rows)
        return result
