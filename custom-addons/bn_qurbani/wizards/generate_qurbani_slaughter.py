from odoo import models, fields
from odoo.exceptions import UserError


class GenerateQurbaniSlaughter(models.TransientModel):
    _name = 'generate.qurbani.slaughter'
    _description = "Generate Qurbani Slaughter"

    day_id = fields.Many2one('qurbani.day', string="Day")
    hijri_id = fields.Many2one('hijri', string="Hijri")
    slaughter_location_id = fields.Many2one('stock.location', string="Slaughter Location")

    pos_product_id = fields.Many2one('product.product', string="POS Product")
    inventory_product_id = fields.Many2one('product.product', string="Inventory Product")
    

    def action_generate_slaughter(self):
        self.ensure_one()

        Demand = self.env['qurbani.slaughter.slot.demand']

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
            SlaughterModel = self.env['qurbani.cow.slaughter']
        elif 'goat' in product_name:
            SlaughterModel = self.env['qurbani.goat.slaughter']
        else:
            raise UserError("Unknown product type! Define Cow or Goat.")

        for demand in demands:

            # 🔹 Count existing records
            existing_count = SlaughterModel.search_count([
                ('day_id', '=', demand.day_id.id),
                ('hijri_id', '=', demand.hijri_id.id),
                ('slaughter_location_id', '=', demand.slaughter_location_id.id),
                ('start_time', '=', demand.start_time),
                ('end_time', '=', demand.end_time),
            ])

            total_hissa = demand.total_hissa or 0
            remaining_hissa = total_hissa - existing_count

            if remaining_hissa <= 0:
                continue

            # 🔹 Create records
            vals_list = []
            for i in range(remaining_hissa):
                vals_list.append({
                    'hijri_id': demand.hijri_id.id,
                    'day_id': demand.day_id.id,
                    'slaughter_location_id': demand.slaughter_location_id.id,
                    'start_time': demand.start_time,
                    'end_time': demand.end_time,
                    'hissa_name': f"Hissa {existing_count + i + 1}",
                })

            SlaughterModel.create(vals_list)