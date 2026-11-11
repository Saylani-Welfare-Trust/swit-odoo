from odoo import models, fields
from odoo.exceptions import UserError

import io
import base64
import xlsxwriter


IBFT_STATUS = [
    ("pending", "Pending"),
    ("success", "Success"),
]


class AccountPayment(models.Model):
    _inherit = "account.payment"

    
    ibft_status = fields.Selection(selection=IBFT_STATUS, string="Printing Status", default="pending", tracking=True)
    ibft_batch_no = fields.Char(string="IBFT Batch No", copy=False, readonly=True, index=True)

    def action_confirm_ibft(self):
        if not self:
            return False

        batch_nos = set(self.filtered('ibft_batch_no').mapped('ibft_batch_no'))
        if len(batch_nos) > 1:
            raise UserError(_(
                "Selected payments belong to different IBFT batches (%s). "
                "Select payments of one batch only.") % ", ".join(sorted(batch_nos)))

        # Already confirmed before: ask for a reason first
        if batch_nos:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Reprint IBFT'),
                'res_model': 'ibft.reprint.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_batch_no': batch_nos.pop(),
                    'default_payment_ids': [(6, 0, self.ids)],
                },
            }
        return self._do_confirm_ibft()

    def _do_confirm_ibft(self, batch_no=False):
        batch_no = batch_no or self.env['ir.sequence'].next_by_code('ibft.batch.number')
        self.write({
            'ibft_status': 'success',
            'ibft_batch_no': batch_no,
        })

        # Generate Excel
        output = io.BytesIO()

        workbook = xlsxwriter.Workbook(output, {
            'in_memory': True
        })

        worksheet = workbook.add_worksheet('Payments')

        headers = [
            'Amount Signed',
            'Recipient Bank Account/Account Holder Name',
            'Recipient Bank Account/Account Number',
            'Customer/Vendor/Banks',
            'Customer/Vendor/Tax ID',
        ]

        header_format = workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'text_wrap': True,
        })

        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        worksheet.set_column(0, 0, 20)
        worksheet.set_column(1, 1, 40)
        worksheet.set_column(2, 2, 35)
        worksheet.set_column(3, 3, 30)
        worksheet.set_column(4, 4, 25)

        # Populate all selected payments
        for row, payment in enumerate(self, start=1):

            worksheet.write_number(
                row, 0,
                payment.amount_signed or 0
            )

            worksheet.write(
                row, 1,
                payment.partner_id.bank_ids[0].acc_holder_name if payment.partner_id.bank_ids else ''
            )

            worksheet.write_string(
                row, 2,
                payment.partner_id.bank_ids[0].acc_number if payment.partner_id.bank_ids else ''
            )

            worksheet.write(
                row, 3,
                payment.partner_id.bank_ids[0].bank_id.name if payment.partner_id.bank_ids else ''
            )

            worksheet.write(
                row, 4,
                payment.partner_id.vat or ''
            )

        workbook.close()
        output.seek(0)

        # Create Excel attachment
        attachment = self.env['ir.attachment'].create({
            'name': 'IBFT_%s.xlsx' % batch_no.replace('/', '_'),
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'mimetype': (
                'application/vnd.openxmlformats-officedocument'
                '.spreadsheetml.sheet'
            ),
            'res_model': self._name,
            'res_id': self[0].id,
        })

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }