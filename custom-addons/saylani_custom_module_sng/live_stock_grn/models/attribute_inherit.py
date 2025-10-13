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
        wizard = self.env['receive.by.weight.wizard'].search([
            ('picking_id', '=', self.id)
        ], limit=1)

        if not wizard:
            wizard = self.env['receive.by.weight.wizard'].create({
                'picking_id': self.id,
            })

        return {
            'name': 'Receive by Weight',
            'type': 'ir.actions.act_window',
            'res_model': 'receive.by.weight.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }
