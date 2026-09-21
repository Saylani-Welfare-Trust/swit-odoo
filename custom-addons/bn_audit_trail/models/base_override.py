# -*- coding: utf-8 -*-
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# Technical / internal models that are NEVER audited, regardless of any
# configuration in Audit Rules - either because it would be pure noise, or
# because auditing them risks recursion (the audit log's own tables) or a
# meaningful performance hit on core Odoo machinery. Since v1.1.0, every
# OTHER model is audited (Create/Update/Delete) by default - this list is
# the only hardcoded exception, everything else is opt-out via the UI.
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
    needing to touch a single line of any other module. Create/Update/Delete
    are audited for every model by default; Audit Rules is used to turn
    specific operations OFF for specific (usually high-volume, low-value)
    models, and to turn View/Read tracking ON where it's actually wanted.
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

        if method == 'read':
            # View/Read tracking is opt-in ONLY: it's the highest-volume
            # event type by far (every form/list open triggers reads), so
            # it must be explicitly switched on per model.
            return bool(rule and rule.get('log_read'))

        # Create / Update / Delete are audited by default for every model.
        # A rule here is only needed to turn a specific operation OFF for
        # a given model (typically a high-volume technical model you've
        # decided isn't worth logging) - no rule at all means "audit it".
        if rule is None:
            return True
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

    def read(self, fields=None, load='_classic_read'):
        audit_enabled = False
        try:
            audit_enabled = bool(self._ids) and self._audit_is_enabled('read')
        except Exception:
            _logger.exception('Audit Trail: failed to check read audit for %s', self._name)

        result = super().read(fields=fields, load=load)

        try:
            if audit_enabled:
                self.env['audit.trail.log']._log_read(self._name, result)
        except Exception:
            _logger.exception('Audit Trail: failed to log read for %s', self._name)
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
