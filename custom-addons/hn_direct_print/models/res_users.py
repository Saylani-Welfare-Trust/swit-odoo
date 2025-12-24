from odoo import models, fields, api
from odoo.exceptions import UserError


class ResUsers(models.Model):
    _inherit = 'res.users'

    enabled_direct_print = fields.Boolean(string="Enable Direct Print", default=False, help="Enable direct printing for this user.")
    printer_name = fields.Char(string="Default Printer Name", help="Name of the default printer for this user.")
