from odoo import _, models, fields
from odoo.exceptions import AccessError, UserError

import io
import base64
import xlsxwriter


IBFT_STATUS = [
    ("pending", "Pending"),
    ("success", "Success"),
]


class AccountPayment(models.Model):
    _inherit = "account.payment"

    
    ibft_status = fields.Selection(selection=IBFT_STATUS, string="IBFT Status", default="pending", tracking=True)


    def action_confirm_ibft(self):

        if not self:
            return False
        if not self.env.user.has_group('account.group_account_invoice'):
            raise AccessError(_('Only accounting users can confirm an IBFT.'))
        wrong = self.filtered(lambda p: p.state != 'posted' or p.payment_type != 'outbound')
        if wrong:
            raise UserError(_('Only posted outgoing payments are sent by IBFT:\n%s')
                            % '\n'.join(wrong.mapped('display_name')))
        done = self.filtered(lambda p: p.ibft_status == 'success')
        if done:
            raise UserError(_('These payments were already confirmed by IBFT:\n%s')
                            % '\n'.join(done.mapped('display_name')))
        no_bank = self.filtered(lambda p: not (p.partner_bank_id or p.partner_id.bank_ids))
        if no_bank:
            raise UserError(_('These payments have no recipient bank account:\n%s')
                            % '\n'.join(no_bank.mapped('display_name')))

        # Update all selected payment statuses
        self.write({
            'ibft_status': 'success'
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
                (payment.partner_bank_id or payment.partner_id.bank_ids[:1]).acc_holder_name or ''
            )

            worksheet.write_string(
                row, 2,
                (payment.partner_bank_id or payment.partner_id.bank_ids[:1]).acc_number or ''
            )

            worksheet.write(
                row, 3,
                (payment.partner_bank_id or payment.partner_id.bank_ids[:1]).bank_id.name or ''
            )

            worksheet.write(
                row, 4,
                payment.partner_id.vat or ''
            )

        workbook.close()
        output.seek(0)

        # Create Excel attachment
        attachment = self.env['ir.attachment'].create({
            'name': 'IBFT_Success_Payments.xlsx',
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