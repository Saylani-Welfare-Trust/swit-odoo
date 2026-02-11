from odoo import models, fields


class LivestockCuttingMaterialLine(models.Model):
    _name = 'livestock.cutting.material.line'
    _description = "Livestock Cutting Material Line"


    livestock_cutting_material_id = fields.Many2one('livestock.cutting.material', string='Livestock Cutting Material')

    product_id = fields.Many2one('product.product', string='Product')

    quantity = fields.Float('Quantity')