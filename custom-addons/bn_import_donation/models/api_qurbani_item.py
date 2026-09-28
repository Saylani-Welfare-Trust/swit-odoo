from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class ApiQurbaniOrderLine(models.Model):
    _name = 'api.qurbani.order.line'
    _description = "Api Qurbani Order Line"


    qurbani_order_id = fields.Many2one('api.donation', string="Qurbani Order")
    city = fields.Char('City Name')
    branch = fields.Char('Branch')
    day = fields.Char('Day')

    qurbani_fullfilment = fields.Char('Qurbani Fullfilment')
    name = fields.Char('Name', default="New")
    hissa_name = fields.Char('Hissa Name')

    start_time = fields.Float('Start Time')
    end_time = fields.Float('End Time')

    donation_type = fields.Char('Donation Type')
    donation_no = fields.Char('Donation No')
    price_id = fields.Char('Price Id')
    price = fields.Float('Price')
    total = fields.Float('Total')
    type = fields.Char('Type')
    item = fields.Char('Item')
    qty = fields.Float('QTY')
    
    is_priced_item = fields.Boolean('Is Priced Item')
