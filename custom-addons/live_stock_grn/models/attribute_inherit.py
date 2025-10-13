from odoo import models, fields

class ProductAttributeValue(models.Model):
    _inherit = 'product.attribute.value'

    from_kg = fields.Float(string='From (kg)')
    to_kg = fields.Float(string='To (kg)')


from odoo import models

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def action_open_receive_by_weight(self):
        # Search for existing wizard (not mandatory, but useful)
        # wizard = self.env['receive.by.weight.wizard'].search([
        #     ('picking_id', '=', self.id)
        # ], limit=1)
        #
        # if not wizard:
        #     wizard = self.env['receive.by.weight.wizard'].create({
        #         'picking_id': self.id,
        #     })

        self.ensure_one()
        print(">>> Opening wizard for picking:", self.name, "id:", self.id)

        Wizard = self.env['receive.by.weight.wizard']
        lines = []
        s_no = 1
        for move in self.move_ids:
            qty = int(move.product_uom_qty or 0)
            print(">>> Move:", move.product_id.display_name, "Qty:", qty)
            for _ in range(qty):
                lines.append((0, 0, {
                    's_no': s_no,
                    'product_id': move.product_id.id,
                    'quantity': 1.0,
                }))
                s_no += 1

        wizard = Wizard.create({
            'picking_id': self.id,
            'line_ids': lines,
        })
        print(">>> Wizard created with ID:", wizard.id, "and lines:", wizard.line_ids)

        return {
            'name': 'Receive by Weight',
            'type': 'ir.actions.act_window',
            'res_model': 'receive.by.weight.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    livestock_variant = fields.Many2one(
        comodel_name='livestock.variant',
        string='Livestock Variant',
        required=False)


    purchase_product = fields.Many2one(
        comodel_name='product.product',
        relation='livestock_product',
        string='Purchase Product',
        help='Product you will make PO',
        required=False)

    main_attribute_id = fields.Many2one(
        comodel_name='product.attribute',
        string='Main Attribute',
        help='When set, only this attribute\'s values are used to determine the highest to_kg.'
    )



class LiveStockVariant(models.Model):
    _name = 'livestock.variant'
    _description = 'Livestock Variant'





    name = fields.Char(
        string='Name',
        required=False)