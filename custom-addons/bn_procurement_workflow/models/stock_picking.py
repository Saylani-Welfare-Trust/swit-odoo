# -*- coding: utf-8 -*-
from odoo import models, _
from odoo.exceptions import UserError

CONFIRM_TO_BILL_GROUP = 'bn_procurement_workflow.group_confirm_to_bill'


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def action_create_bill(self):
        """Creating the vendor bill from a receipt is the "Confirm to Bill" step."""
        if not self.env.user.has_group(CONFIRM_TO_BILL_GROUP):
            raise UserError(_('Only a user with the "Confirm to Bill" right can create the bill from a receipt.'))
        return super().action_create_bill()
