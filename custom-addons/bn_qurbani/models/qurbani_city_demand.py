from odoo import models, fields, api
from odoo.exceptions import UserError


class QurbaniCityDemand(models.Model):
    _name = 'qurbani.city.demand'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = 'Qurbani City Demand'

    # --------------------------------
    # BASIC FIELDS
    # --------------------------------
    hijri_id = fields.Many2one('hijri', string="Hijri", tracking=True)
    day_id = fields.Many2one('qurbani.day', string="Day", tracking=True)
    city_location_id = fields.Many2one('stock.location', string='City', tracking=True)
    inventory_product_id = fields.Many2one('product.product', string='Inventory Product', tracking=True)

    demand = fields.Integer('Demand', tracking=True)
    total_demand = fields.Integer('Cumulative Demand', compute="_compute_total_demand", store=True, tracking=True)
    remaining_demand = fields.Integer('Remaining Demand', compute="_compute_remaining_demand", store=True, tracking=True)

    slaughter_location_ids = fields.Many2many('stock.location', string="Slaughter Location")


    # --------------------------------
    # CITY DEMAND COMPUTE
    # --------------------------------
    @api.depends('demand')
    def _compute_total_demand(self):
        for record in self:
            if record.demand > 0:
                record.total_demand += record.demand

    @api.depends('demand')
    def _compute_remaining_demand(self):
        for record in self:
            if record.demand < 0:
                if record.remaining_demand + record.demand >= 0:
                    record.remaining_demand += record.demand
                    record.total_demand += record.demand
            elif record.demand > 0:
                record.remaining_demand += record.demand

    def action_open_chatter(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'qurbani.city.demand',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }