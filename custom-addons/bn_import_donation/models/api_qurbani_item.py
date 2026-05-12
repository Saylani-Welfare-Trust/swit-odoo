from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ApiQurbaniOrderLine(models.Model):
    _name = 'api.qurbani.order.line'
    _description = "Api Qurbani Order Line"


    qurbani_order_id = fields.Many2one('api.donation', string="Qurbani Order", ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Product",     ondelete='cascade')
    city_id = fields.Many2one('stock.location', string="City", ondelete='set null')
    distribution_id = fields.Many2one('stock.location', string="Distribution", ondelete='set null')
    day_id = fields.Many2one('qurbani.day', string="Day", ondelete='set null')
    hijri_id = fields.Many2one('hijri', string="Hijri", ondelete='set null')

    name = fields.Char('Name', default="New")
    hissa_name = fields.Char('Hissa Name')

    start_time = fields.Float('Start Time')
    end_time = fields.Float('End Time')

    quantity = fields.Integer('Quantity', default=1)

    amount = fields.Float('Amount')
    active = fields.Boolean('Active', default=True)

    def unlink(self):
        """Archive instead of hard delete to avoid constraint violations"""
        try:
            return super().unlink()
        except Exception as e:
            # If deletion fails due to constraints, archive instead
            _logger.warning(f"Deletion failed for api.qurbani.order.line, archiving instead: {str(e)}")
            self.write({'active': False})
            return True
