from odoo import models, fields

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
        self.ensure_one()

        self.ibft_status = "success"

        output = io.BytesIO()

        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Payments')

        # Excel Headers (same as your provided format)
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
            'text_wrap': True,
            'valign': 'vcenter',
        })

        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        # Column widths
        worksheet.set_column(0, 0, 18)
        worksheet.set_column(1, 1, 40)
        worksheet.set_column(2, 2, 35)
        worksheet.set_column(3, 3, 35)
        worksheet.set_column(4, 4, 25)

        # Populate selected payment records
        for row, payment in enumerate(self, start=1):

            worksheet.write(row, 0, payment.amount_signed or 0)

            worksheet.write(
                row, 1,
                payment.partner_bank_id.acc_holder_name or ''
            )

            worksheet.write(
                row, 2,
                payment.partner_bank_id.acc_number or ''
            )

            worksheet.write(
                row, 3,
                payment.partner_bank_id.bank_id.name or ''
            )

            worksheet.write(
                row, 4,
                payment.partner_id.vat or ''
            )

        workbook.close()
        output.seek(0)

        # Create downloadable Excel attachment
        attachment = self.env['ir.attachment'].create({
            'name': 'IBFT_Success_Payments.xlsx',
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'res_model': self._name,
            'res_id': self.id,
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }