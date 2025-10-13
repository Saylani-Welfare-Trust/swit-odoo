from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date, timedelta


class HrWeek(models.Model):
    _name = "week.week"
    _description = "Hr Weeks"

    name = fields.Char(string="Name")
    code = fields.Char(string="Day No")
    l_code = fields.Char(string="Leave Code")
    duration_type_id = fields.Many2one('hr.duration.type', string="Type")

class WeekSelection(models.Model):
    _name = 'week.selection'
    _description = "Week Selection"

    name = fields.Char(string="Name")
    code = fields.Char(string="No")

class HrDurationType(models.Model):
    _name = "hr.duration.type"
    _description = "Hr Duration Type"

    name = fields.Char(string="Name")
