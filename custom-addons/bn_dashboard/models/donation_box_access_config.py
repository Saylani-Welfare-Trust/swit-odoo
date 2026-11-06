from odoo import models, fields, api

# ⚡ FIX: Changed from TransientModel to Model
class DonationBoxAccessConfig(models.Model):
    _name = 'donation.box.access.config'
    _description = 'Donation Box Access Configuration'
    _rec_name = 'name'

    name = fields.Char(string='Rule Name', required=True, default="New Rule")
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
        if self.operation == 'replace':
            for user in self.user_ids:
                user.donation_box_analytic_ids = [(6, 0, self.analytic_ids.ids)]
        else:
            for user in self.user_ids:
                for a in self.analytic_ids:
                    if self.operation == 'add':
                        user.donation_box_analytic_ids = [(4, a.id)]
                    elif self.operation == 'remove':
                        user.donation_box_analytic_ids = [(3, a.id)]
        
        # ⚡ Optional: Show a success notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': 'Locations updated successfully for the selected users!',
                'type': 'success',
                'sticky': False,
            }
        }