from odoo import models, fields, api
from odoo.exceptions import UserError


class QurbaniSlaughterSlotDemand(models.Model):
    _name = "qurbani.slaughter.slot.demand"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Qurbani Slaughter Slot Demand"

    
    day_id = fields.Many2one("qurbani.day", string="Day", tracking=True)
    hijri_id = fields.Many2one("hijri", string="Hijri", tracking=True)
    slaughter_location_id = fields.Many2one('stock.location', string="Slaughter Location", tracking=True)
    inventory_product_id = fields.Many2one('product.product', string='Inventory Product', tracking=True)

    start_time = fields.Float(string="Start Time", tracking=True)
    end_time = fields.Float(string="End Time", tracking=True)

    slaughter_remaining_demand = fields.Integer('Slaughter Demand', compute="_compute_slaughter_remaining_demand")
    demand = fields.Integer(string="Demand", tracking=True)
    total_demand = fields.Integer('Cumulative Demand', compute="_compute_total_demand", store=True, tracking=True)
    remaining_demand = fields.Integer('Remaining Demand', compute="_compute_remaining_demand", store=True, tracking=True)
    total_hissa = fields.Integer('Total Hissa', compute="_compute_total_hissa", store=True, tracking=True)
    booked_hissa = fields.Integer('Booked Hissa', default=0, tracking=True)
    current_hissa = fields.Integer('Current Hissa', default=0, tracking=True)
    remaining_hissa = fields.Integer('Remaining Hissa', compute="_compute_remaining_hissa", store=True, tracking=True)

    distribution_location_ids = fields.Many2many('stock.location', string="Distribution Locations")


    @api.depends('total_hissa', 'booked_hissa')
    def _compute_remaining_hissa(self):
        for record in self:
            record.remaining_hissa = record.total_hissa - record.booked_hissa

    @api.depends('demand')
    def _compute_total_hissa(self):
        for record in self:
            hissa_per_unit = 0

            if record.inventory_product_id:
                name = record.inventory_product_id.name.lower()

                if 'cow' in name:
                    hissa_per_unit = 7
                elif 'goat' in name:
                    hissa_per_unit = 1

            record.total_hissa = int(hissa_per_unit * record.total_demand)

    @api.depends('demand')
    def _compute_slaughter_remaining_demand(self):
        for record in self:
            slaughter_demand = self.env['qurbani.slaughter.demand'].search([
                ('day_id', '=', record.day_id.id),
                ('hijri_id', '=', record.hijri_id.id),
                ('slaughter_location_id', '=', record.slaughter_location_id.id),
                ('inventory_product_id', '=', record.inventory_product_id.id)
            ], limit=1)

            record.slaughter_remaining_demand = slaughter_demand.remaining_demand if slaughter_demand else 0

    @api.onchange('demand')
    def check_demand(self):
        for record in self:
            slaughter_demand = self.env['qurbani.slaughter.demand'].search([
                ('day_id', '=', record.day_id.id),
                ('hijri_id', '=', record.hijri_id.id),
                ('slaughter_location_id', '=', record.slaughter_location_id.id),
                ('inventory_product_id', '=', record.inventory_product_id.id),
            ], limit=1)

            if not slaughter_demand:
                raise UserError("No slaughter demand found for the selected day, hijri date, and slaughter location.")

            if slaughter_demand and record.demand > slaughter_demand.remaining_demand:
                raise UserError(f"Slaughter demand cannot exceed slaughter demand of {slaughter_demand.remaining_demand}.")
            
            slaughter_demand.remaining_demand -= record.demand
            
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
                    hissa_per_unit = 0

                    if record.inventory_product_id:
                        name = record.inventory_product_id.name.lower()

                        if 'cow' in name:
                            hissa_per_unit = 7
                        elif 'goat' in name:
                            hissa_per_unit = 1

                    record.total_hissa = int(hissa_per_unit * record.total_demand)
            elif record.demand > 0:
                record.remaining_demand += record.demand

    def action_open_chatter(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'qurbani.slaughter.slot.demand',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }