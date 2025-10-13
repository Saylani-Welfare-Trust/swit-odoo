from odoo import models

class PartnerXlsx(models.AbstractModel):
    _name = 'report.microfinance_loan.bulk_upload_pxc_template'
    _inherit = 'report.report_xlsx.abstract'

    def many2many_xlsx(self, loopvalue):
        # Convert Many2many field data to a string to Excel report.
        list_val = []
        for val in loopvalue:
            list_val.append(val.name)
        list_str = ' | '.join(list_val)
        return list_str


    def generate_xlsx_report(self, workbook, data, mfd_loan):
        bold = workbook.add_format({'bold': True})
        bg_yellow_format = workbook.add_format({'bold': True, 'align': 'center', 'bg_color': 'yellow'})
        pdc_sheet = workbook.add_worksheet('Post Date Cheques')
        pdc_sheet.set_column('A:E', 25)

        row = 0
        col = 0

        pdc_sheet.write(row, col, 'Installment ID', bg_yellow_format)
        pdc_sheet.write(row, col + 1, 'Cheque Number', bg_yellow_format)
        pdc_sheet.write(row, col + 2, 'Bank Name', bg_yellow_format)
        pdc_sheet.write(row, col + 3, 'Amount', bg_yellow_format)
        pdc_sheet.write(row, col + 4, 'Cheque Date', bg_yellow_format)


        for line in mfd_loan.loan_reqeust_lines:
            row += 1
            pdc_sheet.write(row, col, line.installment_id)
            pdc_sheet.write(row, col+3, line.cheque_amount)
