from odoo import api, fields, models, _

status_selection = [
    ('draft', 'Draft'),
    ('validate', 'Validate'),
    ('box_open', 'Open Box'),
    ('valuation_committee', 'Valuation Committee'),
    ('approval', 'Approval'),
    ('box_validate', 'Box Validate'),
    ('cancel', 'Cancelled')
]

class ProductValuationLineModel(models.Model):
    _name = 'product.valuation.lines'
    _description = 'Product Valuation Line Model'
    _rec_name = 'product_id'

    def default_set_value(self, name):
        product_stock_move_config = self.env['product.stock.move.config'].sudo().search([], limit=1)
        if product_stock_move_config:
            field_map = {
                'location_id': product_stock_move_config.location_id.id
            }
            return field_map.get(name, False)
        return False

    product_id = fields.Many2one(comodel_name='product.product', string='Product', required=True,domain="[('detailed_type', '=', 'product')]")
    location_id = fields.Many2one(comodel_name='stock.location', string='Location', required=True,domain="[('usage', '=', 'internal')]",default=lambda self: self.default_set_value('location_id'))
    quantity = fields.Float(string='Quantity', required=True)
    avg_price = fields.Float(string='Average Price', required=True)
    price_bool = fields.Boolean(string='Price Bool', compute='compute_price_bool', store=True, default=False)
    check_price_bool = fields.Boolean(string='Check Price Bool', default=False)
    product_stock_move_id = fields.Many2one(comodel_name='product.stock.move', string='Product Stock Move',required=True)
    product_stock_move_line_id = fields.Many2one(comodel_name='product.stock.move.lines', string='Product Stock Move Line')
    company_id = fields.Many2one(comodel_name='res.company', string='Company', default=lambda self: self.env.company)
    name = fields.Char(string="Reference", default=lambda self: _('New'))
    state = fields.Selection(related='product_stock_move_id.state', selection=status_selection, string='State')

    @api.constrains('product_id', 'avg_price')
    @api.onchange('product_id', 'avg_price')
    def compute_price_bool(self):
        for record in self:
            if record.avg_price == 0.0:
                record.price_bool = True
            elif not record.avg_price:
                record.price_bool = True
            else:
                record.price_bool = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('product.valuation.lines.sequence')
        return super(ProductValuationLineModel, self).create(vals_list)

    def name_get(self):
        result = []
        for record in self:
            name = f'{record.product_id.name}'
            result.append((record.id, name))
        return result

    @api.constrains('product_id')
    @api.onchange('product_id')
    def constraint_product_id(self):
        for record in self:
            if record.product_id:
                record.avg_price = record.product_id.lst_price
            else:
                record.avg_price = 0

