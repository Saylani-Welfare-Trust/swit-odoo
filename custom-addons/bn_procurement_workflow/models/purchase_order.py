# -*- coding: utf-8 -*-
from odoo import models, _


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def action_cxo_approve_po(self):
        """CXO approval on this RFQ is the only CXO approval in the Procurement
        workflow - reflect it onto the requisition's own state so the PR
        doesn't need a second, duplicate CXO Approval step of its own."""
        res = super().action_cxo_approve_po()
        for order in self:
            requisition = order.requisition_id
            if requisition and requisition.selected_rfq_id == order and requisition.state == 'vendor_selected':
                requisition.write({'state': 'cxo_approved'})
                requisition.message_post(body=_('CXO approved the selected RFQ %s.') % order.name)
        return res

    def action_hod_approve_po(self):
        """Likewise for HOD approval - once recorded on the winning RFQ, the
        requisition moves straight to the Funds Availability gate."""
        res = super().action_hod_approve_po()
        for order in self:
            requisition = order.requisition_id
            if requisition and requisition.selected_rfq_id == order and requisition.state == 'cxo_approved':
                requisition.write({'state': 'funds_check'})
                requisition.message_post(body=_(
                    'HOD approved the selected RFQ %s - moving to Funds Availability check.'
                ) % order.name)
        return res
