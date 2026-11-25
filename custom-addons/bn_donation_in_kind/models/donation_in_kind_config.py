from odoo import _, api, fields, models
from odoo.exceptions import UserError


class DonationInKindConfig(models.Model):
    _name = 'donation.in.kind.config'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Donation In Kind Config"


    location_id = fields.Many2one('stock.location', string='Location')
    picking_type_id = fields.Many2one('stock.picking.type', string='Operations Types',
                                      domain=[('program_type', '=', 'donation_in_kind')])
    journal_id = fields.Many2one('account.journal', string='Journal')

    @api.model_create_multi
    def create(self, vals_list):
        # one setup only: a second record would leave the choice to chance
        if self.sudo().search_count([]) + len(vals_list) > 1:
            raise UserError(_("There is already a Donation In Kind configuration: edit it instead of adding another."))
        return super().create(vals_list)
