from odoo import models, fields


class UpdateQurbaniDemand(models.TransientModel):
    _name = 'update.qurbani.demand'
    _description = 'Update Qurbani Demand'


    hijri_id = fields.Many2one('hijri', string="Hijri")
    day_id = fields.Many2one('qurbani.day', string="Day")

    slaughter_location_id = fields.Many2one('stock.location', string='Slaughter Location')

    demand = fields.Float('Demand')


    def action_update_demand(self):
        if self.hijri_id and self.day_id and self.slaughter_location_id and self.demand:
            demand = self.env['qurbani.demand'].search([('hijri_id', '=', self.hijri_id.id), ('day_id', '=', self.day_id.id), ('slaughter_location_id', '=', self.slaughter_location_id.id)])
            if demand:
                for record in demand:
                    record.city_demand += self.demand
