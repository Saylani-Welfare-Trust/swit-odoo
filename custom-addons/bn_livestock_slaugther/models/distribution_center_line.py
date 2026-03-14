from odoo import models, fields


class DistributionCenterLine(models.Model):
    _name = 'distribution.center.line'
    _description = "Distribution Center Line"


    distribution_center_id = fields.Many2one('distribution.center', string="Distribution Center")
    product_id= fields.Many2one('product.product', string="Product")

    quantity = fields.Float('Quantity', default=1)