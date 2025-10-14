# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.tools import SQL
import re
import logging
_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = 'stock.move'

    def get_next_sno(self):
        picking_type = self.picking_id.picking_type_id
        query = """
            select
                sl.name as lot_name
            from
                stock_move sm
                join stock_move_line sml on sml.move_id =sm.id
                join stock_lot sl on  sml.lot_id = sl.id
            where
                sml.lot_id is not null
                and sm.picking_type_id = %(picking_type_id)s
                and sm.company_id = %(company_id)s
            order by sl.name DESC
            limit 1
        """

        # query = """
        #     select
        #         sml.lot_name
        #     from
        #         stock_move sm
        #         join stock_move_line sml on sml.move_id =sm.id
        #     where
        #         sml.lot_name is not null and
        #         sm.picking_type_id = %(picking_type_id)s and
        #         sm.company_id = %(company_id)s
        #     order by sml.lot_name DESC
        #     limit 1
        # """

        self._cr.execute(SQL(query, picking_type_id=picking_type.id, company_id=self.company_id.id))
        data_dict = self._cr.dictfetchone()
        highest_name = data_dict.get('lot_name', False)
        _logger.info(f'get_next_sno; \nhighest lot_name in stock move line = {highest_name}\n'
                     f'picking_type_id={picking_type.id}\n'
                     f'move={self.name}, ref={self.reference}')
        if highest_name:
            match = re.search(r'(\d+)$', highest_name)
            # Extract number and increment
            num = str(int(match.group(1)) + 1).zfill(len(match.group(1)))
            # Replace the number at the end
            new_lot_name = highest_name[:match.start(1)] + num
            return new_lot_name
        else:
            return False
