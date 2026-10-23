# -*- coding: utf-8 -*-
from odoo import models, _
from odoo.exceptions import UserError

PROCUREMENT_MANAGER_GROUP = 'bn_procurement_workflow.group_procurement_manager'


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def action_create_bill(self):
        """Creating the vendor bill from a receipt is the Procurement Manager's step."""
        if not self.env.user.has_group(PROCUREMENT_MANAGER_GROUP):
            raise UserError(_('Only a Procurement Manager can create the bill from a receipt.'))
        return super().action_create_bill()
