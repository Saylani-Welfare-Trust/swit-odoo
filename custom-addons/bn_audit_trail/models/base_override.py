# -*- coding: utf-8 -*-
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# Every model is audited (Create, Update, Delete, View) by default. This
# fixed set is always excluded, no matter what - hardcoded, not
# database/UI-configured, so it can't be accidentally changed or go stale.
# These are internal Odoo plumbing models where logging would either
# recurse on itself (the audit log's own tables) or be high-volume,
# low-value noise (document numbering, cron, bus, mail bookkeeping,
# attachments). For excluding OTHER models via the UI, see
# audit.trail.exclusion (Audit Trail > Excluded Models) below.
#
# To add another permanent, code-level exclusion, add its technical name
# here and redeploy - this set is deliberately not meant to be end-user
# editable.
AUDIT_EXCLUDED_MODELS = {
    'audit.trail.log',
    'audit.trail.log.line',
    'audit.trail.exclusion',
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


class Base(models.AbstractModel):
    """Inheriting 'base' patches EVERY model in the registry - built-in
    (res.partner, sale.order, account.move, ...) and custom alike - without
    needing to touch a single line of any other module.

    Policy: Create / Update / Delete / View are audited for every model
    by default, except:
      * AUDIT_EXCLUDED_MODELS above - fixed, code-level, not configurable.
      * Models listed in Audit Trail > Excluded Models (audit.trail.exclusion)
        - a small, purpose-built config screen for turning specific models
        off, with a correctly-invalidated cache (see that model for why
        this matters).
    """
    _inherit = 'base'

    # -----------------------------------------------------------------
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
            excluded = self.env['audit.trail.exclusion'].sudo()._get_excluded_model_names()
        except Exception:
            excluded = set()
        if self._name in excluded:
            return False
        return True

    # -----------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        try:
            if records and self._audit_is_enabled():
                self.env['audit.trail.log']._log_create(records, vals_list)
        except Exception:
            _logger.exception('Audit Trail: failed to log create for %s', self._name)
        return records

    def write(self, vals):
        audit_enabled = False
        old_values = {}
        try:
            audit_enabled = self._audit_is_enabled()
            if audit_enabled:
                tracked = [f for f in vals.keys() if f in self._fields]
                # Fetch pre-write values for the diff without that internal
                # fetch itself generating a spurious View/read log entry.
                snapshot = self.with_context(_audit_trail_skip_read=True)
                old_values = {
                    rec.id: {f: rec[f] for f in tracked}
                    for rec in snapshot
                }
        except Exception:
            _logger.exception('Audit Trail: failed to snapshot old values for %s', self._name)

        result = super().write(vals)

        try:
            if audit_enabled:
                self.env['audit.trail.log']._log_write(self, vals, old_values)
        except Exception:
            _logger.exception('Audit Trail: failed to log write for %s', self._name)
        return result

    def _read_format(self, fnames, load='_classic_read'):
        # Hooked here rather than on read() - Odoo 17's web client mostly
        # calls web_read()/web_search_read(), not the classic read(); both
        # of those, and classic read() itself, all funnel through
        # _read_format() internally. Hooking this one method catches every
        # access path (browser UI, RPC, XML-RPC) uniformly.
        result = super()._read_format(fnames, load=load)
        try:
            if (self._ids and not self.env.context.get('_audit_trail_skip_read')
                    and self._audit_is_enabled()):
                self.env['audit.trail.log']._log_read(self._name, result)
        except Exception:
            _logger.exception('Audit Trail: failed to log read for %s', self._name)
        return result

    def unlink(self):
        audit_enabled = False
        snapshot = {}
        try:
            audit_enabled = self._audit_is_enabled()
            if audit_enabled:
                snapshot = {rec.id: self.env['audit.trail.log']._safe_display_name(rec)
                            for rec in self}
        except Exception:
            _logger.exception('Audit Trail: failed to snapshot records for %s', self._name)

        result = super().unlink()

        try:
            if audit_enabled and snapshot:
                self.env['audit.trail.log']._log_unlink(self._name, snapshot)
        except Exception:
            _logger.exception('Audit Trail: failed to log unlink for %s', self._name)
        return result
