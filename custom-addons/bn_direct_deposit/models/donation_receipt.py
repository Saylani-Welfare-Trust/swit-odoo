from odoo import models, fields


class DonationReceipt(models.Model):
    _inherit = 'advance.donation.receipt'

    direct_deposit_id = fields.Many2one('direct.deposit', string="Direct Deposit", readonly=True, copy=False)

    def _get_pos_source_record(self):
        source = super()._get_pos_source_record()
        if source:
            return source
        if self.direct_deposit_id:
            return self.direct_deposit_id

        # Receipts created before the links were stored only carry their
        # source in the cheque number / remarks.
        if self.payment_type == 'cheque' and self.cheque_number:
            order = self.env['pos.order'].search([
                ('pos_cheque_id.name', '=', self.cheque_number),
                ('partner_id', '=', self.donor_id.id),
            ], limit=1)
            if order:
                return order
        if self.remarks and 'Direct Deposit' in self.remarks:
            return self.env['direct.deposit'].search([('name', '=', self.remarks.split()[-1])], limit=1)
        return source

    def _get_pos_source_report(self, source):
        if source._name == 'direct.deposit':
            return self.env.ref('bn_direct_deposit.report_direct_deposit_dn')
        return super()._get_pos_source_report(source)
