# -*- coding: utf-8 -*-
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# Technical / internal models that must never be audited, either because
# it would be noise, or because auditing them could cause recursion
# (the audit log models themselves) or heavy performance cost.
AUDIT_EXCLUDED_MODELS = {
    'audit.trail.log',
    'audit.trail.log.line',
    'audit.trail.rule',
    'ir.logging',
    'ir.cron',
    'ir.cron.trigger',
    'ir.attachment',
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
    needing to touch a single line of any other module. This is what lets
    the Audit Rules screen enable tracking on any model with zero code.
    """
    _inherit = 'base'

    # -----------------------------------------------------------------
    def _audit_is_enabled(self, method):
        if self._transient or self._abstract:
            return False
        if self._name in AUDIT_EXCLUDED_MODELS:
            return False
        if not self.env.registry.ready:
            # Avoid querying our own tables while they're still being
            # created during this module's own installation.
            return False
        try:
            rules = self.env['audit.trail.rule'].sudo()._get_active_rules()
        except Exception:
            return False
        rule = rules.get(self._name)
        if not rule:
            return False
        return bool(rule.get('log_%s' % method))

    # -----------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        try:
            if records and self._audit_is_enabled('create'):
                self.env['audit.trail.log']._log_create(records, vals_list)
        except Exception:
            _logger.exception('Audit Trail: failed to log create for %s', self._name)
        return records

    def write(self, vals):
        audit_enabled = False
        old_values = {}
        try:
            audit_enabled = self._audit_is_enabled('write')
            if audit_enabled:
                tracked = [f for f in vals.keys() if f in self._fields]
                old_values = {
                    rec.id: {f: rec[f] for f in tracked}
                    for rec in self
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

    def unlink(self):
        audit_enabled = False
        snapshot = {}
        try:
            audit_enabled = self._audit_is_enabled('unlink')
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
