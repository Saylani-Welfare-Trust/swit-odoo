from odoo import models,fields,api
from odoo.exceptions import UserError
import openpyxl
import base64
from io import StringIO, BytesIO



class ResCompany(models.Model):
    _inherit = 'res.company'

    upload_attachment_id = fields.Binary(string="Attach Data")
    upload_attachment_name = fields.Char()

    def upload_company_data(self):
        if not self.upload_attachment_id:
            raise UserError("Please Upload PDC file.")
        # Ensure the file is uploaded and has the correct extension
        if not self.upload_attachment_name.lower().endswith('.xlsx'):
            raise UserError("Please upload a valid .xlsx file.")

        file_content = base64.b64decode(self.upload_attachment_id)
        xlsx_file = BytesIO(file_content)

        try:
            workbook = openpyxl.load_workbook(xlsx_file, data_only=True)
        except Exception as e:
            raise UserError(f"Error opening the Excel file: {e}")

        sheet = workbook.active

        # Read the XLSX data
        for row in sheet.iter_rows(min_row=2, values_only=True):  # Start reading from the second row
            if not row:
                continue

            company_name = row[0]
            address = row[1]
            city = row[2]
            state_id = row[3]
            country_id = row[4]
            parent_company_id = row[5]

            print(company_name, 'company_name')
            print(address, 'address')
            print(city, 'city')
            print(state_id, 'state_id')
            print(country_id, 'country_id')
            print(parent_company_id, 'parent_company_id')

            self.env['res.company'].create({
                'name': company_name,
                'street':address,
                'city': city,
                'state_id': state_id,
                'country_id': country_id,
                'parent_id': parent_company_id,
            })
