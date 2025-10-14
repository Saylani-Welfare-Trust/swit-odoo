from odoo import fields, models, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    gen_donation_req_picking = fields.Boolean(
        config_parameter='donation_box_sp.gen_donation_req_picking',
    )
    donation_box_sp_type = fields.Many2one(
        'stock.picking.type',
        config_parameter='donation_box_sp.donation_box_sp_type',
    )