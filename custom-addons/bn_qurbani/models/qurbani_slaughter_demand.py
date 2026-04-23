from odoo import models, fields, api
from odoo.exceptions import UserError


class QurbaniSlaughterDemand(models.Model):
    _name = "qurbani.slaughter.demand"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Qurbani Slaughter Demand"

    day_id = fields.Many2one("qurbani.day", string="Day", tracking=True)
    hijri_id = fields.Many2one("hijri", string="Hijri Date", tracking=True)

    city_location_id = fields.Many2one('stock.location', string="City Location", tracking=True)
    slaughter_location_id = fields.Many2one('stock.location', string="Slaughter Location", tracking=True)
    inventory_product_id = fields.Many2one('product.product', string='Inventory Product', tracking=True)
    
    city_remaining_demand = fields.Integer('City Demand', compute="_compute_city_remaining_demand")
    demand = fields.Integer(string="Demand", tracking=True)
    total_demand = fields.Integer('Cumulative Demand', compute="_compute_total_demand", store=True, tracking=True)
    remaining_demand = fields.Integer('Remaining Demand', compute="_compute_remaining_demand", store=True, tracking=True)


    @api.depends('demand')
    def _compute_city_remaining_demand(self):
        for record in self:
            city_demand = self.env['qurbani.city.demand'].search([
                ('day_id', '=', record.day_id.id),
                ('hijri_id', '=', record.hijri_id.id),
                ('city_location_id', '=', record.city_location_id.id),
                ('inventory_product_id', '=', record.inventory_product_id.id)
            ], limit=1)

            record.city_remaining_demand = city_demand.remaining_demand if city_demand else 0

    @api.onchange('demand')
    def check_demand(self):
        for record in self:
            city_demand = self.env['qurbani.city.demand'].search([
                ('day_id', '=', record.day_id.id),
                ('hijri_id', '=', record.hijri_id.id),
                ('slaughter_location_ids', 'in', [record.slaughter_location_id.id]),
                ('inventory_product_id', '=', record.inventory_product_id.id)
            ], limit=1)

            if not city_demand:
                raise UserError("No city demand found for the selected day, hijri date, and slaughter location.")

            if city_demand and record.demand > city_demand.remaining_demand:
                raise UserError(f"Slaughter demand cannot exceed city demand of {city_demand.remaining_demand}.")
            
            city_demand.remaining_demand -= record.demand
            

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
            'res_model': 'qurbani.slaughter.demand',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }