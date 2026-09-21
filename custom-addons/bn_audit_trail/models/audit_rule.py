# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools


class AuditTrailRule(models.Model):
    """Exceptions list for auditing, not a whitelist.

    Create/Update/Delete are audited for EVERY model by default (see
    models/base_override.py) - you do not need a row here to start
    auditing a model. Add a row here only to:
      * turn OFF specific operations for a specific (typically
        high-volume, low business value) model, or
      * turn ON View/Read tracking for a model, which stays opt-in only.
    """
    _name = 'audit.trail.rule'
    _description = 'Audit Trail Rule'
    _rec_name = 'model_id'

    model_id = fields.Many2one(
        'ir.model', string='Model', required=True, ondelete='cascade',
        domain=[('transient', '=', False)],
        help="The model this exception applies to. Every model is audited "
             "(Create/Update/Delete) by default - only add a row here to "
             "change that for a specific model.",
    )
    model_name = fields.Char(related='model_id.model', store=True, readonly=True,
                              string='Technical Name')
    log_create = fields.Boolean(
        string='Log Create', default=True,
        help="Untick to stop logging new records of this model. "
             "Ticked (or no rule at all) = audited, which is the default "
             "for every model.")
    log_write = fields.Boolean(
        string='Log Update', default=True,
        help="Untick to stop logging edits to records of this model. "
             "Ticked (or no rule at all) = audited, which is the default "
             "for every model.")
    log_unlink = fields.Boolean(
        string='Log Delete', default=True,
        help="Untick to stop logging deletions of records of this model. "
             "Ticked (or no rule at all) = audited, which is the default "
             "for every model.")
    log_read = fields.Boolean(
        string='Log View (Read)', default=False,
        help="Logs every time a user opens/views a record of this model - "
             "i.e. who read which record, and when. Off by default and "
             "NOT audited unless you tick this here: this is the "
             "highest-volume type of log (every form/list open counts), "
             "so enable it selectively on models where 'who looked at "
             "this' actually matters (e.g. donor records, payroll, HR "
             "files).",
    )
    active = fields.Boolean(
        default=True,
        help="If unchecked, this exception is ignored and the model falls "
             "back to full default auditing (Create/Update/Delete on, "
             "View off).")

    _sql_constraints = [
        ('model_uniq', 'unique(model_id)',
         'An audit exception already exists for this model.'),
    ]

    @api.model
    @tools.ormcache()
    def _get_active_rules(self):
        """Cached lookup: {model_technical_name: {log_create, log_write,
        log_unlink, log_read}} for every model that has an EXPLICIT
        exception row. A model with no entry here is audited under the
        default policy (Create/Update/Delete on, View off) - see
        _audit_is_enabled() in models/base_override.py.

        Cached in memory per-database so the check on every create/write/
        unlink/read across the whole system is cheap. NOTE: this cache is
        NOT auto-cleared when a rule changes (see README "Cache note") -
        restart the service or upgrade the module after editing rules.
        """
        self.env.cr.execute("""
            SELECT im.model, r.log_create, r.log_write, r.log_unlink, r.log_read
            FROM audit_trail_rule r
            JOIN ir_model im ON im.id = r.model_id
            WHERE r.active = true
        """)
        return {
            row[0]: {
                'log_create': row[1],
                'log_write': row[2],
                'log_unlink': row[3],
                'log_read': row[4],
            }
            for row in self.env.cr.fetchall()
        }

    @api.model_create_multi
    def create(self, vals_list):
        """Self-healing create: if an exception row for a given model
        already exists - active OR archived (Odoo hides archived rows from
        the default list view, so they're easy to forget about) - update
        and reactivate that row instead of raising a unique-constraint
        error. Also merges duplicate models within the same batch."""
        to_create = []
        seen_at = {}
        result_records = self.browse()
        for vals in vals_list:
            model_id = vals.get('model_id')
            if not model_id:
                to_create.append(vals)
                continue
            if model_id in seen_at:
                # Same model appears twice in this one call - merge into
                # the entry already queued instead of creating two rows.
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
            result_records |= super(AuditTrailRule, self).create(to_create)
        return result_records

    def write(self, vals):
        res = super().write(vals)
        return res

    def unlink(self):
        res = super().unlink()
        return res
