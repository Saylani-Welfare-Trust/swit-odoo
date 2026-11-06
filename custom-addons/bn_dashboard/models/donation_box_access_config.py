from odoo import api, fields, models


class DonationBoxAccessConfig(models.TransientModel):
    _name = 'donation.box.access.config'
    _description = 'Donation Box Access Configuration'

    user_ids = fields.Many2many(
        'res.users', string='Users', required=True,
    )
    analytic_ids = fields.Many2many(
        'account.analytic.account', string='Locations', required=True,
        domain="[('plan_id.name', '=', 'Location')]",
    )
    operation = fields.Selection([
        ('add',     'Add to existing'),
        ('remove',  'Remove from existing'),
        ('replace', 'Replace existing'),
    ], string='Operation', default='add', required=True)

    def action_apply(self):
        self.ensure_one()
        cmds = {
            'add':     lambda a: [(4, a.id)],
            'remove':  lambda a: [(3, a.id)],
            'replace': lambda a: [(6, 0, self.analytic_ids.ids)],
        }[self.operation]
        if self.operation == 'replace':
            for user in self.user_ids:
                user.donation_box_analytic_ids = [(6, 0, self.analytic_ids.ids)]
        else:
            for user in self.user_ids:
                user.donation_box_analytic_ids = [cmds(a)[0] for a in self.analytic_ids]
        return {'type': 'ir.actions.act_window_close'}