from odoo import models, fields, api
from odoo.exceptions import UserError


class meat_requisition(models.Model):
    _name = 'meat.requisition'
    _description = 'meat.requisition'
    _rec_company_auto = True

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    type = fields.Selection(
        string='Type',
        selection=[('meat', 'Meat'),
                   ('live_stock', 'Live Stock'), ],
        required=False, )

    material_from = fields.Many2one(
        comodel_name='res.company',
        string='Material From?',
        required=False)

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

    line_ids = fields.One2many(
        'meat.requisition.line',
        'requisition_id',
        string='Lines',
    )






class MeatRequisitionLine(models.Model):
    _name = 'meat.requisition.line'
    _description = 'Meat Material Requisition Line'

    requisition_id = fields.Many2one(
        'meat.requisition',
        ondelete='cascade',
        required=True
    )

    product_id = fields.Many2one('product.product', string='Product', )
    quantity = fields.Float(string='Qty', required=True)
    uom_id = fields.Many2one('uom.uom', string='UoM',)
    meat_category = fields.Boolean(
        # related='product_id.categ_id.is_meat',
        string='Is Meat',
        readonly=True,
    )






