from odoo import models, fields


class GenerateQurbaniSlaughter(models.TransientModel):
    _name = 'generate.qurbani.slaughter'
    _description = "Generate Qurbani Slaughter"


    day_id = fields.Many2one('qurbani.day', string="Day")
    hijri_id = fields.Many2one('hijri', string="Hijri")

    slaughter_location_id = fields.Many2one('stock.location', string="Slaughter Location")

    pos_product_id = fields.Many2one('product.product', string="POS Product")
    inventory_product_id = fields.Many2one('product.product', string="Inventory Product")

    inventory_product_name = fields.Char(related='inventory_product_id.name', string="Inentory Product Name")


    def action_generate_slaughter(self):
        pass