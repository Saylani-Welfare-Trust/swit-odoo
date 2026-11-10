# -*- coding: utf-8 -*-
from odoo import models, _
from odoo.exceptions import ValidationError


class VendorSelectionWizard(models.TransientModel):
    _inherit = 'vendor.selection.wizard'

    def action_create_rfqs(self):
        requisition = self.source_requisition_id
        if requisition and (requisition.state != 'procurement_review' or not requisition.procurement_manager_id):
            raise ValidationError(
                _('RFQs can only be created once the Procurement Manager has approved this '
                  'Purchase Requisition for RFQ.'))
        result = super().action_create_rfqs()
        if requisition:
            requisition.action_mark_rfq_sent()
        return result
