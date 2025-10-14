from odoo import models, fields, api
from odoo.exceptions import UserError


class POS_requisition(models.Model):
    _name = 'pos.requisition'
    _description = 'pos.requisition'
    _rec_company_auto = True

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    type = fields.Selection(
        string='Type',
        selection=[('meat', 'Meat'),
                   ('live_stock', 'Live Stock'), ],
        required=False, )

    # product = fields.Many2one('product.template', string="Product", required=True)


    meat_type = fields.Selection(
        string='Meat Type',
        selection=[('cow', 'Cow'),
                   ('Goat', 'Goat'),
                   ('camel', 'Camel'),
                   ],
        required=False, )


    live_stock_type = fields.Selection(
        string='Live Stock Type',
        selection=[('cow', 'Cow'),
                   ('Goat', 'Goat'),
                   ('camel', 'Camel'),
                   ],
        required=False, )

    quantity = fields.Float(
        string='Quantity',
        required=False)

    delivery_location = fields.Char(
        string='Delivery Location',
        required=False)

    date = fields.Date(
        string='Date',
        required=False)

    material_from = fields.Many2one(
        comodel_name='res.company',
        string='Material From?',
        required=False)

    state = fields.Selection(
        string='State',
        selection=[('draft', 'Draft'),
                   ('confirmed', 'Confirmed'), ],
        default='draft',
        required=False, )




    def action_confirm(self):
        meat_requisition_obj = self.env['meat.requisition']
        live_stock_requisition_obj = self.env['live_stock.requisition']
        for record in self:
            if record.state == 'draft':
                if record.type == 'meat':
                    meat_requisition_obj.create({
                        'type': record.type,
                        'meat_type': record.meat_type,
                        'live_stock_type': record.live_stock_type,
                        'quantity': record.quantity,
                        'delivery_location': record.delivery_location,
                        'date': record.date,
                        'material_from': record.material_from.id,

                    })
                elif record.type == 'live_stock':
                    live_stock_requisition_obj.create({
                        'type': record.type,
                        'meat_type': record.meat_type,
                        'live_stock_type': record.live_stock_type,
                        'quantity': record.quantity,
                        'delivery_location': record.delivery_location,
                        'date': record.date,
                        'material_from': record.material_from.id,
                    })

                record.state = 'confirmed'


