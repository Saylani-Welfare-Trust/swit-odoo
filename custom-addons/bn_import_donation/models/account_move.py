from odoo import models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'


    import_donation_id = fields.Many2one('import.donation', string="Import Donation", tracking=True)
    
    
    def action_post(self):
        res = super(AccountMove, self).action_post()
        for move in self:
            if move.import_donation_id:
                for donation in self.env['donation'].search([('import_donation_id', '=', move.import_donation_id.id)]):
                    donation.state = 'posted'
        return res