from odoo import models, fields, api

class PackCategory(models.Model):
    _name = 'ration.pack.category'
    _description = 'Ration Pack Category'

    name = fields.Many2one( 'product.template',required=True)

    product_id = fields.Char(string='Product ID', compute='_compute_product_id', store=True)

    @api.depends('name')
    def _compute_product_id(self):
        for rec in self:
            rec.product_id = str(rec.name.id) if rec.name else False


    pack_line_ids = fields.One2many(
        'ration.pack.line', 'category_id', string="Pack Lines"
    )

    state = fields.Selection(
        string='State',
        selection=[('draft', 'Draft'),
                   ('approved', 'Approved'), ],
        default='draft',
        required=False, )

    def create_bom_for_category(self):
        for pack in self:
            # Prepare the current recipe as a dictionary: {product_id: quantity}
            current_recipe = {
                line.product_id.id: line.quantity
                for line in pack.pack_line_ids
            }

            # Search for existing BoMs for this product template
            existing_boms = self.env['mrp.bom'].search([
                ('product_tmpl_id', '=', pack.name.id),
                ('type', '=', 'normal')
            ])

            # Check if an identical BoM already exists
            bom_exists = False
            for bom in existing_boms:
                # Prepare the BoM's recipe as a dictionary
                bom_recipe = {
                    line.product_id.id: line.product_qty
                    for line in bom.bom_line_ids
                }
                if bom_recipe == current_recipe:
                    bom_exists = True
                    break

            # Create a new BoM only if an identical one doesn't exist
            if not bom_exists:
                self.env['mrp.bom'].create({
                    'product_tmpl_id': pack.name.id,
                    'type': 'normal',
                    'bom_line_ids': [(0, 0, {
                        'product_id': line.product_id.id,
                        'product_qty': line.quantity
                    }) for line in pack.pack_line_ids]
                })

            pack.write({'state':'approved'})


class PackLine(models.Model):
    _name = 'ration.pack.line'
    _description = 'Pack Line Detail'

    category_id = fields.Many2one(
        'ration.pack.category', required=True, ondelete='cascade'
    )
    product_id = fields.Many2one(
        'product.product', required=True, string="Ingredient"
    )
    quantity = fields.Float(required=True, string="Qty per Pack")
