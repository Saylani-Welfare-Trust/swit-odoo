# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools


class AuditTrailRule(models.Model):
    """Configuration: which model(s) get audited, and for which operations.

    This is the on/off switch. Adding a rule here for ANY model - standard
    (res.partner, sale.order, ...) or custom (x_my_module.my_model) - turns
    on logging for it immediately, with no code change required.
    """
    _name = 'audit.trail.rule'
    _description = 'Audit Trail Rule'
    _rec_name = 'model_id'

    model_id = fields.Many2one(
        'ir.model', string='Model', required=True, ondelete='cascade',
        domain=[('transient', '=', False)],
        help="The model to audit. Works for built-in and custom models alike.",
    )
    model_name = fields.Char(related='model_id.model', store=True, readonly=True,
                              string='Technical Name')
    log_create = fields.Boolean(string='Log Create', default=True)
    log_write = fields.Boolean(string='Log Update', default=True)
    log_unlink = fields.Boolean(string='Log Delete', default=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('model_uniq', 'unique(model_id)',
         'An audit rule already exists for this model.'),
    ]

    @api.model
    @tools.ormcache()
    def _get_active_rules(self):
        """Cached lookup: {model_technical_name: {log_create, log_write, log_unlink}}.

        Cached in memory per-database so the check on every create/write/unlink
        across the whole system is cheap. Cache is cleared whenever a rule is
        created, edited or removed (see below).
        """
        self.env.cr.execute("""
            SELECT im.model, r.log_create, r.log_write, r.log_unlink
            FROM audit_trail_rule r
            JOIN ir_model im ON im.id = r.model_id
            WHERE r.active = true
        """)
        return {
            row[0]: {
                'log_create': row[1],
                'log_write': row[2],
                'log_unlink': row[3],
            }
            for row in self.env.cr.fetchall()
        }

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._get_active_rules.clear_cache(self)
        return records

    def write(self, vals):
        res = super().write(vals)
        self._get_active_rules.clear_cache(self)
        return res

    def unlink(self):
        res = super().unlink()
        self._get_active_rules.clear_cache(self)
        return res
