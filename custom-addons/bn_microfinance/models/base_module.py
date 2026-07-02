from odoo import models, fields, api, _
import UserError, ValidationError

class BaseModule(models.Model):
    _inherit = 'base'

    def unlink(self):
        raise UserError(_('You cannot delete a record.'))
