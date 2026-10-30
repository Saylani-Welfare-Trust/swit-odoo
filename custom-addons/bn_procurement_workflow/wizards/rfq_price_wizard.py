# -*- coding: utf-8 -*-
from odoo import models, fields, _
from odoo.exceptions import ValidationError

RFQ_SELECTION_GROUP = 'bn_procurement_workflow.group_rfq_selection'


class RFQPriceWizard(models.TransientModel):
    _inherit = 'rfq.price.wizard'

    designated_cxo_approver_id = fields.Many2one(
        'master.cxo.approver',
        string='Assigned CXO Approver',
        help='Assigned to the RFQs selected with "Confirm Selected Lines": '
             'ONLY this user can give them CXO approval.')

    def action_confirm_selected(self):
        """Entering prices is open to everyone who can use the wizard; picking
        the winning quote needs the RFQ Selection right - matching the
        visibility of the selection boxes and of the button."""
        if not self.env.user.has_group(RFQ_SELECTION_GROUP):
            raise ValidationError(_('Only a user with the RFQ Selection right can select the winning quote.'))
        if not self.designated_cxo_approver_id:
            raise ValidationError(_('Please select the CXO Approver before confirming the selected lines.'))
        return super().action_confirm_selected()

    def _confirm_rfq(self, rfq):
        """RFQs linked to a requisition under the Procurement workflow are not
        confirmed immediately - the winning one is marked as selected and
        waits for CXO + HOD approval directly on that RFQ, then Funds Check,
        before it can ever be confirmed. Each product of the requisition gets
        its own winning RFQ."""
        # Before the selection, which emails the approver once the RFQ is selected
        rfq.designated_cxo_approver_id = self.designated_cxo_approver_id
        requisition = rfq.requisition_id
        if requisition and requisition._is_selecting_rfqs():
            requisition.action_select_winning_rfq(rfq)
        else:
            super()._confirm_rfq(rfq)
