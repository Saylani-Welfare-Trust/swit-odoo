from odoo import models, fields
from odoo.exceptions import ValidationError


class UpdateQurbaniDemand(models.TransientModel):
    _name = 'update.qurbani.demand'
    _description = 'Update Qurbani Demand'


    slaughter_slot_demand_id = fields.Many2one('qurbani.slaughter.slot.demand', string='Slaughter Slot Demand')
    demand = fields.Float('Demand')


    def update_demand(self):
        for wizard in self:
            wizard.slaughter_slot_demand_id.demand = wizard.demand

            wizard.slaughter_slot_demand_id._update_demand()