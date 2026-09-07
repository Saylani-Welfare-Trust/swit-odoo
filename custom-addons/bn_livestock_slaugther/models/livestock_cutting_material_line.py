from odoo import models, fields, api


class LivestockCuttingMaterialLine(models.Model):
    _name = 'livestock.cutting.material.line'
    _description = "Livestock Cutting Material Line"


    livestock_cutting_material_id = fields.Many2one('livestock.cutting.material', string='Livestock Cutting Material')
    livestock_slaughter_id = fields.Many2one('livestock.slaugther', string='Livestock Slaughter')
    is_material_request_line = fields.Boolean(
        string='Material Request Line',
        compute='_compute_is_material_request_line',
    )

    product_id = fields.Many2one('product.product', string='Product')

    quantity = fields.Float('Quantity')

    def _compute_is_material_request_line(self):
        for line in self:
            line.is_material_request_line = line.livestock_cutting_material_id.state == 'not_received'