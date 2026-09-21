# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools


class AuditTrailExclusion(models.Model):
    """Models listed here are fully excluded from auditing - no Create,
    Update, Delete or View logs will be created for them - while every
    other model keeps being audited by default (see AUDIT_EXCLUDED_MODELS
    in models/base_override.py for the small, fixed, code-level list that
    is excluded no matter what and isn't meant to be end-user configurable).

    This is a deliberately minimal, one-purpose screen: add a model here
    only if you've decided its activity genuinely isn't worth logging
    (e.g. a very high-frequency technical/detail model).
    """
    _name = 'audit.trail.exclusion'
    _description = 'Audit Trail Exclusion'
    _rec_name = 'model_id'

    model_id = fields.Many2one(
        'ir.model', string='Model', required=True, ondelete='cascade',
        domain=[('transient', '=', False)],
        help="Activity on this model will NOT be logged at all "
             "(no Create/Update/Delete/View entries) while this "
             "exclusion is active.",
    )
    model_name = fields.Char(related='model_id.model', store=True,
                              readonly=True, string='Technical Name')
    reason = fields.Char(string='Reason',
                          help="Optional note on why this model is excluded.")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('model_uniq', 'unique(model_id)',
         'This model is already in the exclusion list.'),
    ]

    # -----------------------------------------------------------------
    @api.model
    @tools.ormcache()
    def _get_excluded_model_names(self):
        """Cached set of technical model names currently excluded.

        Cached in memory so the check on every create/write/unlink/read
        across the whole system is cheap. Cleared via self.clear_caches()
        below on every create/write/unlink of this model - this is the
        documented, stable Odoo API for clearing a model's own ormcache
        entries (unlike env.registry.clear_caches(), which an earlier
        version of this module called and which did not reliably clear
        anything - that's why toggling a setting used to silently not
        take effect).
        """
        self.env.cr.execute("""
            SELECT im.model
            FROM audit_trail_exclusion e
            JOIN ir_model im ON im.id = e.model_id
            WHERE e.active = true
        """)
        return {row[0] for row in self.env.cr.fetchall()}

    # -----------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """Self-healing create: if an exclusion for a given model already
        exists - active OR archived (Odoo hides archived rows from the
        default list view) - reactivate/update that row instead of
        raising a unique-constraint error. Also merges duplicate models
        within the same batch."""
        to_create = []
        seen_at = {}
        result_records = self.browse()
        for vals in vals_list:
            model_id = vals.get('model_id')
            if not model_id:
                to_create.append(vals)
                continue
            if model_id in seen_at:
                to_create[seen_at[model_id]].update(
                    {k: v for k, v in vals.items() if k != 'model_id'})
                continue
            existing = self.with_context(active_test=False).search(
                [('model_id', '=', model_id)], limit=1)
            if existing:
                existing.write({k: v for k, v in vals.items() if k != 'model_id'})
                if not existing.active:
                    existing.active = True
                result_records |= existing
            else:
                seen_at[model_id] = len(to_create)
                to_create.append(vals)
        if to_create:
            result_records |= super(AuditTrailExclusion, self).create(to_create)
        self.clear_caches()
        return result_records

    def write(self, vals):
        res = super().write(vals)
        self.clear_caches()
        return res

    def unlink(self):
        res = super().unlink()
        self.clear_caches()
        return res
