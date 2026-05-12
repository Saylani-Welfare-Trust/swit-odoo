from odoo import models, fields, _


class QurbaniCowSlaughterLine(models.Model):
    _name = 'qurbani.cow.slaughter.line'
    _description = "Qurbani Cow Slaughter Line"


    qurbani_cow_slaughter_id = fields.Many2one('qurbani.cow.slaughter', string="Qurbani Cow Slaughter")
    product_id = fields.Many2one('product.product', string="Product")

    qurbani_order_no = fields.Char('QO No.')
    qurbani_order_line_no = fields.Char('QOL No.')
    hissa_name = fields.Char('Hissa Name')

    def action_transfer(self):
        return {
            'name': _('Transfer Slaughter'),
            'type': 'ir.actions.act_window',
            'res_model': 'transfer.slaughter',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_qurbani_cow_slaughter_line_id': self.id,
            }
        }