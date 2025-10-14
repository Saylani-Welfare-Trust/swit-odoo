from odoo import models, fields, api, _
from datetime import datetime, timedelta, date
import calendar
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
DEFAULT_FACTURX_DATE_FORMAT = '%m%d%Y'
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


class AllocationWizard(models.TransientModel):
    _name = "allocation.wizard.lines"

    wizard_id = fields.Many2one('allocation.wizard', string="Weeks")
    week_id = fields.Many2one('week.week', string="Day")
    week_selection_ids = fields.Many2many('week.selection', string="Number Of Weekoff")

class AllocationWizard(models.TransientModel):
    _name = "allocation.wizard"
    _description = "allocation.wizard"

    description = fields.Text()
    date_from = fields.Date()
    date_to  = fields.Date()
    shift_id = fields.Many2one("hr.shift", required=True)
    week_ids = fields.One2many('allocation.wizard.lines', 'wizard_id', string="Weeks")
    employee_ids = fields.Many2many("hr.employee", required=True)
    
    @api.model
    def default_get(self, fields):
        vals = super(AllocationWizard, self).default_get(fields)
        active_ids = self.env.context.get('active_ids')
        vals['employee_ids'] = active_ids
        return vals

    def employee_leave(self, employee_id):
        leave_days = []
        leave_ids = self.env['hr.leave'].search([('request_date_from', '>=', self.date_from),('request_date_to', '<=', self.date_to), ('employee_id','=', employee_id.id), ('state', '=', 'validate')])
        for leave in leave_ids:
            from_date = leave.request_date_from
            to_date = leave.request_date_to
            while from_date <= to_date:
                date =  fields.Date.to_string(from_date)
                leave_days.append(str(date))
                from_date += timedelta(days=1)
        return leave_days

    def employee_holiday(self):
        public_holidays = []
        public_holiday_ids = self.env['resource.calendar.leaves'].search([('resource_id', '=', False),('date_from', '>=', self.date_from),('date_to', '<=', self.date_to)])
        for leave in public_holiday_ids:
            curr_date = leave.date_from.date()
            end_date = leave.date_to.date()
            while curr_date <= end_date:
                date = fields.Date.to_string(curr_date)
                public_holidays.append(date)
                curr_date += timedelta(days=1)
        return public_holidays

    def find_week_days(self, week, line):
        # print("\n\n WWEKKKKKKKK", week, line.week_id, line.week_id.code)
        if line.week_id.code == '0':
           days = week[calendar.MONDAY]
        if line.week_id.code == '1':
           days = week[calendar.TUESDAY]
        if line.week_id.code == '2':
           days = week[calendar.WEDNESDAY]
        if line.week_id.code == '3':
           days = week[calendar.THURSDAY]
        if line.week_id.code == '4':
           days = week[calendar.FRIDAY]
        if line.week_id.code == '5':
           days = week[calendar.SATURDAY]
        if line.week_id.code == '6':
           days = week[calendar.SUNDAY]
        return days

    def _prepaire_days_of_week_lines(self, employee_id):
        days_of_week_lines = []
        d_dates = {}
        public_holidays = self.employee_holiday()
        leave_days = self.employee_leave(employee_id)
        if self.date_from and self.date_to:
            date_array = (self.date_from + timedelta(days = x) for x in range(0, ((self.date_to - self.date_from).days)))
            for date_object in date_array:
                month_year = "{}-{}".format(date_object.year, date_object.month)
                if month_year not in d_dates:
                    d_dates.update({month_year:calendar.monthcalendar(date_object.year, date_object.month)})
            # weeks
            for line in self.week_ids:
                for i, cal in d_dates.items():
                    for wk in line.week_selection_ids:
                        if len(cal) > int(wk.code) - 1:
                            week = cal[int(wk.code) - 1]
                            days = self.find_week_days(week, line)
                            if days:
                                days_list = []
                                full_date = "{}-{}".format(i, days)
                                date_obj = datetime.strptime(full_date, DEFAULT_SERVER_DATE_FORMAT)
                                curr_date =  fields.Date.to_string(date_obj)
                                days_list.append(curr_date)
                                check_public_holiday = any(item in days_list for item in public_holidays)
                                chek_employee_leave = any(item in days_list for item in leave_days)
                                if check_public_holiday or chek_employee_leave:
                                    continue
                                else:
                                    if date_obj.date() >= self.date_from and date_obj.date() <= self.date_to:
                                        days_of_week_lines.append((0,0,{
                                            'date': date_obj, 
                                            'week_id': line.week_id.id, 
                                            'employee_id': employee_id.id, 
                                            'shift_id': self.shift_id.id,
                                            'week_selection_id': wk.id,
                                            'create_date': date.today(),
                                            'user_id': self.env.user.id,
                                            'company_id': self.env.user.company_id.id,
                                        }))

        return days_of_week_lines

    def _prepare_shift_value(self):
        return {
            'date_from': self.date_from,
            'date_to': self.date_to,
            'shift_id': self.shift_id.id,
            'shift_type_id': self.shift_id.shift_type_id and self.shift_id.shift_type_id.id,
            'description': self.description,
            'state': 'in_progress',
            'company_id': self.env.user.company_id.id,
        }


    def bulk_allocation(self):
        vals = self._prepare_shift_value()
        public_holidays = self.employee_holiday()
        for emp in self.employee_ids:
            days_of_allocation_line = []
            leave_days = self.employee_leave(emp)
            start_date = self.date_from
            end_date = self.date_to
            total_days = end_date - start_date
            vals['employee_id'] = emp.id
            lines = self._prepaire_days_of_week_lines(emp)
            vals['dayofweek_ids'] = lines
            allocation = self.env['shift.allocation'].create(vals)
            week_off_day = emp.dayofweek_ids.mapped('date')
            total_holiady = public_holidays + week_off_day
            for i in range(total_days.days + 1):
                days_list = []
                date_days =  fields.Date.to_string(start_date)
                days_list.append(date_days)
                check_public_holiday = any(item in days_list for item in public_holidays)
                chek_employee_leave = any(item in days_list for item in leave_days)
                if start_date not in total_holiady and not check_public_holiday and not chek_employee_leave:
                    days_of_allocation_line.append((0,0,{'date': start_date, 'employee_id': emp.id, 'shift_id': self.shift_id.id,  'create_date': date.today(), 'user_id': self.env.user.id, 'company_id': self.env.user.company_id.id}))
                start_date += timedelta(days=1)
            allocation.write({'dayofallocation_ids': days_of_allocation_line})
