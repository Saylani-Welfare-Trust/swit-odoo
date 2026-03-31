from odoo import models, fields


class DailyPlanningLine(models.Model):
    _name = 'daily.planning.line'
    _description = 'Daily Planning Line'


    daily_planning_id = fields.Many2one('daily.planning', string='Daily Planning')

    product_id = fields.Many2one('product.product', string='Product')

    quantity = fields.Float(string='Quantity')