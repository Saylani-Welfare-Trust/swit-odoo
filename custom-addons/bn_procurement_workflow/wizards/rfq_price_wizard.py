# -*- coding: utf-8 -*-
from odoo import models


class RFQPriceWizard(models.TransientModel):
    _inherit = 'rfq.price.wizard'

    def _confirm_rfq(self, rfq):
        """RFQs linked to a requisition under the Procurement workflow are not
        confirmed immediately - they are routed to Technical Evaluation instead."""
        requisition = rfq.requisition_id
        if requisition and requisition.state == 'rfq_sent':
            requisition.action_send_to_technical_evaluation(rfq)
        else:
            super()._confirm_rfq(rfq)
