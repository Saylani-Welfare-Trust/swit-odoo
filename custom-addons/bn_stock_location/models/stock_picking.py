from odoo import models, fields, api


class StockPicking(models.Model):
    _inherit = 'stock.picking'


    user_allowed_location_ids = fields.Many2many(
        'stock.location',
        string="User Allowed Locations",
        compute='_compute_user_allowed_locations',
        store=False
    )

    @api.depends('partner_id')
    def _compute_user_allowed_locations(self):
        for rec in self:
            # Clear the field
            rec.user_allowed_location_ids = [(5, 0, 0)]

            # Assign the user's allowed locations if user exists
            if rec.user_id:
                rec.user_allowed_location_ids = [(6, 0, rec.user_id.allowed_location_ids.ids)]