# -*- coding: utf-8 -*-
from odoo import fields, api, models, _
from odoo.exceptions import ValidationError
from datetime import timedelta
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
import datetime
import pytz
import calendar

import json
import io
from odoo.http import request
from odoo.tools import date_utils

try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    import xlsxwriter

class EmployeeAllocationMuster(models.TransientModel):
    _name = 'employee.allocation.muster'
    _description = "Employee Allocation Muster"

    date_from = fields.Date(string="Date From")
    date_to = fields.Date(string="Date To")

    def action_allocation_xls_report(self):
        active_record = self
        data = {
            'active_record': active_record.id,
        }
        return {
            'type': 'ir.actions.report',
            'data': {
                'model': 'employee.allocation.muster',
                'options': json.dumps(data, default=date_utils.json_default),
                'output_format': 'xlsx',
                'report_name': 'Employee Allocation Days',
            },
            'report_type': 'xlsx'
        }

    def get_xlsx_report(self, data, response):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        active_id = data.get('active_record')
        allocation_id = self.env['employee.allocation.muster'].browse(int(active_id))
        aged_id = self.env['employee.allocation.muster'].browse(int(active_id))
        format1 = workbook.add_format({'font_size': 10, 'align': 'center' , 'bold': True, 'bg_color': '#D3D3D3'})
        format2 = workbook.add_format({'font_size': 10, 'bold': True, 'bg_color': '#D3D3D3'})
        format3 = workbook.add_format({'font_size': 10, 'align': 'left'})
        format4 = workbook.add_format({'font_size': 10, 'align': 'left'})
        format1.set_align('center')
        shift_ids = self.env['hr.shift'].search([])
        for shift in shift_ids:
            recs = {}
            date_from = allocation_id.date_from
            date_too = allocation_id.date_to
            allocation_ids = self.env['shift.allocation'].search([('shift_id', '=', shift.id),('date_from', '>=', date_from), ('date_to', '<=', date_too)])
            delta = date_too - date_from
            # header for shift
            allocation = "%s-%s" % (shift.time_from, shift.time_too)
            sheet = workbook.add_worksheet(shift.name)
            name = "Employee Shift Roster From %s To %s" % (date_from.strftime("%d-%m-%Y"),date_too.strftime("%d-%m-%Y"))
            sheet.merge_range('A1:K1', name , format1)
            row_d1 = 2
            col_d1 = 0
            sheet.write(row_d1 ,col_d1, 'WO :', format1)
            sheet.write(row_d1 ,col_d1+1, 'Weekoff', format1)
            col_d1 += 2
            sheet.write(row_d1 ,col_d1+1, 'N/A :', format1)
            col_d1 += 1
            sheet.write(row_d1 ,col_d1+1, 'Not Available', format1)
            row = 4
            col = 0
            sheet.write(row ,col, 'Employee', format1)
            sheet.write(row ,col+1, 'Department', format1)
            col += 1
            sheet.write(row ,col+1, 'Job Position', format1)
            col += 1
            for i in range(delta.days + 1):
                day = date_from.strftime("%d")
                sheet.write(row ,col+1, day, format1)
                date_from += timedelta(days=1)
                col += 1

            # code start 
            vals = []
            employee_ids = allocation_ids.mapped('employee_id')
            for employee in employee_ids:
                allocation_day = employee.dayofallocation_ids.mapped('date')
                weekoff_day = employee.dayofweek_ids.mapped('date')
                recs.update({employee.name: {}})
                recs[employee.name].update({'department': employee.department_id.name, 'job_position': employee.job_id.name})
                date_from = allocation_id.date_from
                for i in range(delta.days + 1):
                    day = date_from.strftime("%d")
                    if date_from in allocation_day:
                        recs[employee.name].update({day: allocation})
                    elif date_from in weekoff_day:
                        recs[employee.name].update({day: "WO"})
                    else:
                        recs[employee.name].update({day: "NA"})
                    date_from += timedelta(days=1)
            vals.append(recs)

            row_number = 5
            column_number = 0
            col = 1
            row = 5
            for value in vals:
                for key, values in value.items():
                    sheet.write(row_number, column_number, key, format4)
                    row_number += 1
                    col = 0
                    for v1, values in values.items():
                        sheet.write(row, col+1, values , format3)
                        col += 1
                    row += 1
        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()
