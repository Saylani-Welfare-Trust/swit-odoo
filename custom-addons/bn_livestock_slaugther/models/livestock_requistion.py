from odoo import models, fields


type_selection = [
    ('meat', 'Meat'),
    ('live_stock', 'Live Stock')
]


class LiveStockRequisition(models.Model):
    _name = 'livestock.requisition'
    _description = "Livestock Requisition"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = 'delivery_location'


    source_location_id = fields.Many2one('stock.location', string="Source Location")
    destination_location_id = fields.Many2one('stock.location', string="Destination Location")

    type = fields.Selection(selection=type_selection, string="Type")

    delivery_location = fields.Char('Delivery Location')

    date = fields.Date('Date')

    livestock_requisition_line_ids = fields.One2many('livestock.requisition.line', 'livestock_requisition_id', string="Livestock Requisition Lines")
