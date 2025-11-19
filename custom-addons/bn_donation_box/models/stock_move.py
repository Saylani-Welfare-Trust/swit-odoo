from odoo import models
from odoo.exceptions import ValidationError


class StockMove(models.Model):
    _inherit = 'stock.move'


    def action_assign_serial(self):
        """ Opens a wizard to assign SN's name on each move lines.
        """
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("stock.act_assign_serial_numbers")

        next_serial_number = self.env['stock.lot'].search([('product_id', '=', self.product_id.id)], order="id desc", limit=1).name

        if next_serial_number:
            next_serial_number = next_serial_number.split('-')[-1]

            if 'crystal' in self.product_id.name.lower() and 'large' in self.product_id.name.lower():
                next_serial_number = f'CL-{int(next_serial_number)+1}'
            elif 'crystal' in self.product_id.name.lower() and 'small' in self.product_id.name.lower():
                next_serial_number = f'CB-{int(next_serial_number)+1}'
            elif 'iron' in self.product_id.name.lower() and 'large' in self.product_id.name.lower():
                next_serial_number = f'IL-{int(next_serial_number)+1}'
            elif 'without' in self.product_id.name.lower() and 'small' in self.product_id.name.lower():
                next_serial_number = f'WB-{int(next_serial_number)+1}'

        # raise ValidationError(next_serial_number)

        action['context'] = {
            'default_product_id': self.product_id.id,
            'default_move_id': self.id,
            'default_next_serial_number': next_serial_number or '',
        }
        return action