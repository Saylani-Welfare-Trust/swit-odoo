from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class BaseModule(models.Model):
    _inherit = 'base'
    _name = 'base.module'

    def unlink(self):
        raise UserError(_('You cannot delete a record.'))