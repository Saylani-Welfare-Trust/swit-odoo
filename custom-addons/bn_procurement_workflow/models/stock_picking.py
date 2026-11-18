# -*- coding: utf-8 -*-
from odoo import models, _
from odoo.exceptions import UserError

PROCUREMENT_MANAGER_GROUP = 'bn_procurement_workflow.group_confirm_to_bill'


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def action_create_bill(self):
        """Creating the vendor bill from a receipt is the Procurement Manager's step."""
        if not self.env.user.has_group(PROCUREMENT_MANAGER_GROUP):
            raise UserError(_('Only a user in the "Confirm to Bill" group can create the bill from a receipt.'))
        return super().action_create_bill()
