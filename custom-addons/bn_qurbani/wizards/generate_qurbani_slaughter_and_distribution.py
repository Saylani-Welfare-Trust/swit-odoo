from odoo import api, fields, models, _
from odoo.exceptions import UserError


class GenerateQurbaniSlaughterAndDistribution(models.TransientModel):
    _name = 'generate.qurbani.slaughter.and.distribution'
    _description = "Generate Qurbani Slaughter And Distribution"


    hijri_id = fields.Many2one('hijri', string="Hijri")
    day_id = fields.Many2one('qurbani.day', string="Day")
    slaughter_location_id = fields.Many2one('stock.location', string="Slaughter Location")
    inventory_product_id = fields.Many2one('product.product', string="Inventory Product")


    def _get_demands(self):

        Demand = self.env['qurbani.slaughter.slot.demand']

        demands = Demand.search([
            ('day_id', '=', self.day_id.id),
            ('hijri_id', '=', self.hijri_id.id),
            ('slaughter_location_id', '=', self.slaughter_location_id.id),
            ('inventory_product_id', '=', self.inventory_product_id.id),
        ])

        if not demands:
            raise UserError(_("No demand record found!"))

        return demands


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

        raise UserError(_("Unknown product type! Define Cow or Goat."))


    def action_generate_slaughter_and_distribution(self):
        self.ensure_one()

        SlaughterSchedule = self.env['slaughter.schedule']
        DistributionSchedule = self.env['distribution.schedule']

        demands = self._get_demands()
        models = self._get_product_models()

        SlaughterModel = models['slaughter']
        DistributionModel = models['distribution']

        for demand in demands:

            # =====================================================
            # 🔹 GENERATE SLAUGHTER
            # =====================================================

            existing_slaughter_count = SlaughterModel.search_count([
                ('day_id', '=', demand.day_id.id),
                ('hijri_id', '=', demand.hijri_id.id),
                ('slaughter_location_id', '=', demand.slaughter_location_id.id),
                ('start_time', '=', demand.start_time),
                ('end_time', '=', demand.end_time),
            ])

            total_demand = demand.total_demand or 0
            remaining_slaughter = total_demand - existing_slaughter_count

            if remaining_slaughter > 0:

                slaughter_vals = []

                for i in range(remaining_slaughter):
                    slaughter_vals.append({
                        'hijri_id': demand.hijri_id.id,
                        'day_id': demand.day_id.id,
                        'slaughter_location_id': demand.slaughter_location_id.id,
                        'start_time': demand.start_time,
                        'end_time': demand.end_time,
                    })

                SlaughterModel.create(slaughter_vals)

            # =====================================================
            # 🔹 GENERATE DISTRIBUTION
            # =====================================================

            slaughter_schedules = SlaughterSchedule.search([
                ('day_id', '=', demand.day_id.id),
                ('hijri_id', '=', demand.hijri_id.id),
                ('location_id', '=', demand.slaughter_location_id.id),
                ('start_time', '=', demand.start_time),
                ('end_time', '=', demand.end_time),
            ])

            for slaughter_schedule in slaughter_schedules:

                distribution_schedules = DistributionSchedule.search([
                    ('slaughter_schedule_id', '=', slaughter_schedule.id)
                ])

                for distribution_schedule in distribution_schedules:

                    existing_distribution_count = DistributionModel.search_count([
                        ('day_id', '=', distribution_schedule.day_id.id),
                        ('hijri_id', '=', distribution_schedule.hijri_id.id),
                        ('distribution_location_id', '=', distribution_schedule.location_id.id),
                        ('start_time', '=', distribution_schedule.start_time),
                        ('end_time', '=', distribution_schedule.end_time),
                    ])

                    remaining_distribution = (
                        total_demand - existing_distribution_count
                    )

                    if remaining_distribution <= 0:
                        continue

                    distribution_vals = []

                    for i in range(remaining_distribution):
                        distribution_vals.append({
                            'hijri_id': distribution_schedule.hijri_id.id,
                            'day_id': distribution_schedule.day_id.id,
                            'distribution_location_id': distribution_schedule.location_id.id,
                            'start_time': distribution_schedule.start_time,
                            'end_time': distribution_schedule.end_time,
                        })

                    DistributionModel.create(distribution_vals)

        return True