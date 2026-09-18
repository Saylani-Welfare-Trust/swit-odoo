# -*- coding: utf-8 -*-
from odoo import models


class RFQPriceWizard(models.TransientModel):
    _inherit = 'rfq.price.wizard'

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
