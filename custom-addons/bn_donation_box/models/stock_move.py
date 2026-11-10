# -*- coding: utf-8 -*-
import re

from odoo import models


class StockMove(models.Model):
    _inherit = 'stock.move'

    def action_assign_serial(self):
        """ Opens a wizard to assign SN's name on each move lines.
        """
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("stock.act_assign_serial_numbers")

        last_lot = self.env['stock.lot'].search([('product_id', '=', self.product_id.id)], order="id desc", limit=1)
        next_serial_number = last_lot.name

        if next_serial_number:
            # Only the trailing number matters; a last serial without one restarts at 1
            # instead of crashing with a ValueError.
            match = re.search(r'(\d+)\s*$', next_serial_number)
            next_number = int(match.group(1)) + 1 if match else 1
            product_name = (self.product_id.name or '').lower()

            if 'crystal' in product_name and 'large' in product_name:
                next_serial_number = f'CL-{next_number}'
            elif 'crystal' in product_name and 'small' in product_name:
                next_serial_number = f'CB-{next_number}'
            elif 'iron' in product_name and 'large' in product_name:
                next_serial_number = f'IL-{next_number}'
            elif 'without' in product_name and 'small' in product_name:
                next_serial_number = f'WB-{next_number}'
            elif match:
                # Any other product: keep the prefix and zero padding of the last serial.
                digits = match.group(1)
                next_serial_number = f'{last_lot.name[:match.start()]}{next_number:0{len(digits)}d}'
            else:
                next_serial_number = ''

        action['context'] = {
            'default_product_id': self.product_id.id,
            'default_move_id': self.id,
            'default_next_serial_number': next_serial_number or '',
        }
        return action
