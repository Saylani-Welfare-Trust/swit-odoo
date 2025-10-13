from odoo import models, fields, api

class expense_report(models.Model):
    _name = 'expense_report.expense_report'
    _description = 'expense_report.expense_report'


    def action_print_report(self):
        # Reading the start and end dates

        docs = []

        # Fetching records based on the date range
        reimburse_data = self.env['hr.expense'].search([('state', '=', 'approved')])
        print('dataa', reimburse_data)

        for record in reimburse_data:
            # Prepare workload line data for each record

            # Add record details along with workload lines
            docs.append({
                'date': record.date,
                'name': record.name,
                'employee_id': record.employee_id.name,
                'total_amount': record.total_amount,

            })

        # Logging for debugging
        print("docs", docs)

        # Preparing the data to be sent to the report
        report_data = {
            'doc_ids': self.ids,
            'doc_model': self._name,
            't': docs,
            'user': self.env.user,

        }

        print(report_data, 'Report Data')

        # Returning the report action with the prepared data
        return self.env.ref('expense_report.expense_report_pdf').report_action(self, data=report_data)


