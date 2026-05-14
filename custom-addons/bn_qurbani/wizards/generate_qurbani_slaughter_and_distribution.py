from odoo import models, fields
from odoo.exceptions import UserError


type_selection = [
    ('slaughter', 'Slaughter'),
    ('distribution', 'Distribution'),
]


class GenerateQurbaniSlaughterAndDistribution(models.TransientModel):
    _name = 'generate.qurbani.slaughter.and.distribution'
    _description = "Generate Qurbani Slaughter And Distribution"


    type = fields.Selection(selection=type_selection, string="Type", default='slaughter')

    day_id = fields.Many2one('qurbani.day', string="Day")
    hijri_id = fields.Many2one('hijri', string="Hijri")
    slaughter_location_id = fields.Many2one('stock.location', string="Slaughter Location")

    inventory_product_id = fields.Many2one('product.product', string="Inventory Product")
    

    def _get_product_models(self):
        product_name = (self.inventory_product_id.name or "").lower()

        if 'cow' in product_name:
            return {
                'slaughter': self.env['qurbani.cow.slaughter'],
                'distribution': self.env['qurbani.cow.distribution'],
            }

        elif 'goat' in product_name:
            return {
                'slaughter': self.env['qurbani.goat.slaughter'],
                'distribution': self.env['qurbani.goat.distribution'],
            }

        raise UserError("Unknown product type! Define Cow or Goat.")


    def _get_demands(self):
        Demand = self.env['qurbani.slaughter.slot.demand']

        demands = Demand.search([
            ('day_id', '=', self.day_id.id),
            ('hijri_id', '=', self.hijri_id.id),
            ('slaughter_location_id', '=', self.slaughter_location_id.id),
            ('inventory_product_id', '=', self.inventory_product_id.id),
        ])

        if not demands:
            raise UserError("No demand record found!")

        return demands


    def action_generate_slaughter(self):
        self.ensure_one()

        demands = self._get_demands()
        models = self._get_product_models()

        SlaughterModel = models['slaughter']

        for demand in demands:

            existing_count = SlaughterModel.search_count([
                ('day_id', '=', demand.day_id.id),
                ('hijri_id', '=', demand.hijri_id.id),
                ('slaughter_location_id', '=', demand.slaughter_location_id.id),
                ('inventory_product_id', '=', demand.inventory_product_id.id),
                ('start_time', '=', demand.start_time),
                ('end_time', '=', demand.end_time),
            ])

            total_demand = demand.total_demand or 0
            remaining_demand = total_demand - existing_count

            if remaining_demand <= 0:
                continue

            vals_list = []

            for i in range(remaining_demand):
                vals_list.append({
                    'hijri_id': demand.hijri_id.id,
                    'day_id': demand.day_id.id,
                    'slaughter_location_id': demand.slaughter_location_id.id,
                    'inventory_product_id': demand.inventory_product_id.id,
                    'start_time': demand.start_time,
                    'end_time': demand.end_time,
                })

            SlaughterModel.create(vals_list)


    def action_generate_distribution(self):
        self.ensure_one()

        demands = self._get_demands()
        models = self._get_product_models()

        DistributionModel = models['distribution']

        for demand in demands:
            existing_count = DistributionModel.search_count([
                ('day_id', '=', demand.day_id.id),
                ('hijri_id', '=', demand.hijri_id.id),
                ('slaughter_location_id', '=', demand.slaughter_location_id.id),
                ('inventory_product_id', '=', demand.inventory_product_id.id),
                ('start_time', '=', demand.start_time),
                ('end_time', '=', demand.end_time),
            ])

            total_hissa = demand.total_hissa or 0
            remaining_demand = total_hissa - existing_count

            if remaining_demand <= 0:
                continue

            vals_list = []

            for i in range(remaining_demand):
                vals_list.append({
                    'hijri_id': demand.hijri_id.id,
                    'day_id': demand.day_id.id,
                    'inventory_product_id': demand.inventory_product_id.id,
                    'slaughter_location_id': demand.slaughter_location_id.id,
                    'slaughter_start_time': demand.start_time,
                    'slaughter_end_time': demand.end_time,
                })

            DistributionModel.create(vals_list)