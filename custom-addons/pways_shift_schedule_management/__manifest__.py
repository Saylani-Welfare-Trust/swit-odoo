# -*- coding: utf-8 -*-
{
    'name': "Employee Shift Scheduling",
    'version': '1.0.0',
    'category': "Generic Modules/Human Resources",
    'author':'Preciseways',
    'summary': "Create shift and weekends based on define duration. shifts will not be created on leaves or holidays or weekoffs. filters your shift based on shift type or employee or department or job positions. Generate multiple excel shift roaster report",
    'description':""" Employee Shift
                        Shift Allocation
                        Shift Roaster
                        Shift Scheduling
                        weekly shift
                        Monthly shift
                        Daily shift
                        Shift creation
                        Automatic shift """,
    'website': "http://www.preciseways.com",
    'depends': ['hr_contract', 'hr_holidays', 'sm_donation_box'],
    'data': [
                'security/ir.model.access.csv',
                'data/data.xml',
                'views/sub_type_view.xml',             
                'views/hr_employee.xml',                  
                'views/hr_shift.xml',
                'views/shift_allocation_view.xml',
                'wizard/bulk_allocation.xml',
                'wizard/employee_allocation_muster_view.xml',
                'views/week_view.xml',
                'views/hr_weekoff.xml',
                'views/hr_shift_request_view.xml',
                'views/hr_day_allocation.xml',
                'report/shift_allocation_report.xml',       
                'report/report_action.xml',
                'views/week_selection_view.xml',
                # 'data/mail_template.xml',
            ],
    'assets': {
        'web.assets_backend': [
            'pways_shift_schedule_management/static/src/js/action_manager.js',
        ],
    },
    'installable': True,
    'application': True,
    'price': 45.0,
    'currency': 'EUR',
    'images':['static/description/banner.png'],
    'license': 'OPL-1',
}   