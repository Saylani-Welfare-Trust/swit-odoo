from odoo import models


class MicrofinancePDC(models.AbstractModel):
    _name = 'report.bn_microfinance.bulk_upload_pdc'
    _inherit = 'report.report_xlsx.abstract'


    def generate_xlsx_report(self, workbook, data, microfinance):
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


        for line in microfinance.microfinance_line_ids:
            row += 1

            pdc_sheet.write(row, col, line.id)
            pdc_sheet.write(row, col+3, line.amount)
