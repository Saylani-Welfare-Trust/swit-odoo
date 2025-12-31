from odoo import models, fields, api


class ProductValuationCommitteeLine(models.Model):
    _name = 'product.valuation.committee.line'
    _description = "Product Valuation Committee Line"


    def default_set_value(self, name):
        donation_in_kind_config = self.env['donation.in.kind.config'].sudo().search([], limit=1)
        if donation_in_kind_config:
            field_map = {
                'location_id': donation_in_kind_config.location_id.id
            }
            return field_map.get(name, False)
        return False

    product_id = fields.Many2one('product.product', string="Product")
    donation_in_kind_id = fields.Many2one('donation.in.kind', string="Donation In Kind")
    donation_in_kind_line_id = fields.Many2one('donation.in.kind.line', string='Donation In Kind Line')
    location_id = fields.Many2one(comodel_name='stock.location', string='Location', required=True,domain="[('usage', '=', 'internal')]",default=lambda self: self.default_set_value('location_id'))

    quantity = fields.Float('Quantity')
    avg_price = fields.Float('Average Price', required=True)

    price_bool = fields.Boolean('Price Bool', compute='_set_price_bool', store=True, default=False)
    check_price_bool = fields.Boolean('Check Price Bool', default=False)
    
    name = fields.Char('Name', default="New")


    @api.depends('product_id', 'avg_price')
    def _set_price_bool(self):
        for record in self:
            if record.avg_price == 0.0:
                record.price_bool = True
            elif not record.avg_price:
                record.price_bool = True
            else:
               record.price_bool = False

    @api.constrains('product_id')
    def constraint_product_id(self):
        for record in self:
            if record.product_id:
                record.avg_price = record.product_id.lst_price
            else:
                record.avg_price = 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('product_valuation_committee_line')
                
        return super(ProductValuationCommitteeLine, self).create(vals_list)