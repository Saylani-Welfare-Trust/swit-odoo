# -*- coding: utf-8 -*-
from odoo import models, _


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def action_cxo_approve_po(self):
        """CXO approval on this RFQ is the only CXO approval in the Procurement
        workflow - reflect it onto the requisition's own state so the PR
        doesn't need a second, duplicate CXO Approval step of its own.

        If the requisition doesn't have a selected RFQ yet, approving one
        here claims it as the winning quote - this doesn't require having
        gone through the Bulk RFQ Price wizard's "Confirm Selected Lines"
        first, since that's an easy step to miss when there's only one
        vendor to compare anyway."""
        res = super().action_cxo_approve_po()
        for order in self:
            requisition = order.requisition_id
            if not requisition or not requisition.material_request_id:
                continue
            if requisition.state == 'rfq_sent' and not requisition.selected_rfq_id:
                requisition.write({'selected_rfq_id': order.id, 'state': 'cxo_approved'})
                requisition.message_post(body=_(
                    'RFQ %s approved by CXO and claimed as the selected quote.'
                ) % order.name)
            elif requisition.selected_rfq_id == order and requisition.state == 'vendor_selected':
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
