from odoo import models, fields
from odoo.exceptions import UserError


class Hijri(models.Model):
    _name = 'hijri'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = 'Hijri'

    name = fields.Char('Hijri', tracking=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('approved', 'Approved')],
        default='draft',
        tracking=True,
    )

    def action_approve(self):
        self.write({'state': 'approved'})

    def write(self, vals):
        if 'state' not in vals or len(vals) > 1:
            for rec in self:
                if rec.state == 'approved' and not self.env.user.has_group('bn_qurbani.group_hijri_approver'):
                    raise UserError("This record is approved. Only an approver can edit it.")
        return super().write(vals)