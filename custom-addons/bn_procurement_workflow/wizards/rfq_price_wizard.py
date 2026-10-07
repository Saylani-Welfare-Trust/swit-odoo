# -*- coding: utf-8 -*-
from odoo import models, _
from odoo.exceptions import ValidationError

RFQ_SELECTION_GROUP = 'bn_procurement_workflow.group_rfq_selection'


class RFQPriceWizard(models.TransientModel):
    _inherit = 'rfq.price.wizard'

    def action_confirm_selected(self):
        """Entering prices is open to everyone who can use the wizard; picking
        the winning quote needs the RFQ Selection right - matching the
        visibility of the selection boxes and of the button."""
        if not self.env.user.has_group(RFQ_SELECTION_GROUP):
            raise ValidationError(_('Only a user with the RFQ Selection right can select the winning quote.'))
        return super().action_confirm_selected()

    def _confirm_rfq(self, rfq):
        """RFQs linked to a requisition under the Procurement workflow are not
        confirmed immediately - the winning one is marked as selected and
        waits for CXO + HOD approval directly on that RFQ, then Funds Check,
        before it can ever be confirmed."""
        requisition = rfq.requisition_id
        if requisition and requisition.state == 'rfq_sent':
            requisition.action_select_winning_rfq(rfq)
        else:
            super()._confirm_rfq(rfq)
