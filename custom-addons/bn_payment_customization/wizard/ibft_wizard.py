
from odoo import models, fields, _
from markupsafe import Markup


class IbftReprintWizard(models.TransientModel):
    _name = 'ibft.reprint.wizard'
    _description = 'IBFT Reprint Reason'

    batch_no = fields.Char(string='IBFT Batch No', readonly=True, required=True)
    payment_ids = fields.Many2many('account.payment', string='Payments')
    reason = fields.Text(string='Reason', required=True)

    def action_confirm(self):
        self.ensure_one()
        payments = self.payment_ids
        batch_payments = self.env['account.payment'].search(
            [('ibft_batch_no', '=', self.batch_no)])
        added = payments - batch_payments
        removed = batch_payments - payments

        action = payments._do_confirm_ibft(self.batch_no)

        body = Markup("IBFT batch %s reprinted by %s.<br/>Reason: %s") % (
            self.batch_no, self.env.user.name, self.reason)
        if added:
            body += Markup("<br/>Added: %s") % ", ".join(added.mapped('display_name'))
        if removed:
            body += Markup("<br/>Removed: %s") % ", ".join(removed.mapped('display_name'))
        for payment in payments | removed:
            payment.message_post(body=body)
        return action