from odoo import models, fields
from odoo.exceptions import UserError


class GenerateQurbaniDistribution(models.TransientModel):
    _name = 'generate.qurbani.distribution'
    _description = "Generate Qurbani Distribution"

    day_id = fields.Many2one('qurbani.day', string="Day")
    hijri_id = fields.Many2one('hijri', string="Hijri")
    distribtuion_location_id = fields.Many2one('stock.location', string="Distribution Location")

    inventory_product_id = fields.Many2one('product.product', string="Inventory Product")

    inventory_product_name = fields.Char(related='inventory_product_id.name', string="Inentory Product Name")

    pos_product_id = fields.Many2many('product.product', string='POS Products', tracking=True)
    

    def action_generate_distribution(self):
        self.ensure_one()

        Demand = self.env['qurbani.slaughter.slot.demand']
        SlaughterSchedule = self.env['slaughter.schedule']
        DistributionSchedule = self.env['distribution.schedule']

        demands = Demand.search([
            ('day_id', '=', self.day_id.id),
            ('hijri_id', '=', self.hijri_id.id),
            ('slaughter_location_id', '=', self.slaughter_location_id.id),
            ('inventory_product_id', '=', self.inventory_product_id.id),
        ])

        if not demands:
            raise UserError("No demand record found!")

        # 🔹 Decide model based on product
        product_name = (self.inventory_product_id.name or "").lower()

        if 'cow' in product_name:
            DistributionModel = self.env['qurbani.cow.distribution']
        elif 'goat' in product_name:
            DistributionModel = self.env['qurbani.goat.distribution']
        else:
            raise UserError("Unknown product type! Define Cow or Goat.")

        for demand in demands:

            slaughter_schedules = SlaughterSchedule.search([
                ('day_id', '=', demand.day_id.id),
                ('hijri_id', '=', demand.hijri_id.id),
                ('location_id', '=', demand.slaughter_location_id.id),
                ('start_time', '=', demand.start_time),
                ('end_time', '=', demand.end_time),
            ])

            for slaughter_schedule in slaughter_schedules:
                distribution_schedules = DistributionSchedule.search([('slaughter_schedule_id', '=', slaughter_schedule.id)])

                for distribution_schedule in distribution_schedules:
                    # 🔹 Count existing records
                    existing_count = DistributionModel.search_count([
                        ('day_id', '=', distribution_schedule.day_id.id),
                        ('hijri_id', '=', distribution_schedule.hijri_id.id),
                        ('distribution_location_id', '=', distribution_schedule.location_id.id),
                        ('start_time', '=', distribution_schedule.start_time),
                        ('end_time', '=', distribution_schedule.end_time),
                    ])

                    total_demand = demand.total_demand or 0
                    remaining_demand = total_demand - existing_count

                    if remaining_demand <= 0:
                        continue

                    # 🔹 Create records
                    vals_list = []
                    for i in range(remaining_demand):
                        vals_list.append({
                            'hijri_id': distribution_schedule.hijri_id.id,
                            'day_id': distribution_schedule.day_id.id,
                            'slaughter_location_id': distribution_schedule.location_id.id,
                            'start_time': distribution_schedule.start_time,
                            'end_time': distribution_schedule.end_time,
                        })

                    DistributionModel.create(vals_list)