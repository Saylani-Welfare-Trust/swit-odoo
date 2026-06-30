from odoo import models, fields, api
from odoo.exceptions import UserError


class Hijri(models.Model):
    _name = 'hijri'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = 'Hijri'

    name = fields.Char('Hijri', tracking=True)
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('approved', 'Approved'),
        ],
        string='Status',
        default='draft',
        tracking=True,
        copy=False,
    )

    def action_approve(self):
        for rec in self:
            if rec.state == 'approved':
                continue
            rec.state = 'approved'

    def action_reset_to_draft(self):
        for rec in self:
            rec.state = 'draft'

    def write(self, vals):
        # Block edits on approved records unless the user is an approver
        # (or the only change being made is the state itself).
        if set(vals.keys()) - {'state'}:
            for rec in self:
                if rec.state == 'approved' and not self.env.user.has_group('bn_qurbani.group_hijri_approver'):
                    raise UserError("This record is approved and locked. Only an approver can edit it.")
        return super().write(vals)