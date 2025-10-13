from odoo import models, fields, api, _
from odoo.exceptions import UserError


class live_stock_requisition(models.Model):
    _name = 'live_stock.requisition'
    _description = 'live_stock.requisition'
    _rec_company_auto = True

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    material_from = fields.Many2one(
        comodel_name='res.company',
        string='Material From?',
        required=False)

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




    def action_confirm(self):
        """Deduct from our company “Slaughter” and add to material_from company “Slaughter”."""
        self.ensure_one()

        # 1) find the product (assumes you have a product with same name)
        product = self.env['product.product'].search([
            ('name', '=', 'Camel')], limit=1)
        if not product:
            raise UserError(_('No product found for %s') % self.live_stock_type)

        # 2) find source & destination locations
        src_loc = self.env['stock.location'].sudo().search([
            ('name','ilike','Slaughter'),
            ('company_id','=', self.company_id.id)], limit=1)
        dest_loc = self.env['stock.location'].sudo().search([
            ('name','ilike','Slaughter'),
            ('company_id','=', self.material_from.id)], limit=1)


        print(src_loc)
        print(dest_loc)
        print(product)

        print('material_from: ', self.material_from.name)

        if not src_loc or not dest_loc:
            raise UserError(_('Could not find a “Slaughter” location for one of the companies.'))

        # 3) adjust quants (this is the standard way to change on-hand) :contentReference[oaicite:1]{index=1}
        qty = float(self.quantity)
        self.env['stock.quant'].sudo()._update_available_quantity(product, src_loc,  -qty)
        self.env['stock.quant'].sudo()._update_available_quantity(product, dest_loc, qty)

        # 4) mark requisition confirmed
        # self.state = 'confirmed'
        return True



