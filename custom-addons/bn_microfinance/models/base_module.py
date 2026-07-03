from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class GlobalUnlinkRestriction(models.AbstractModel):
    _inherit = 'base'
    _name = 'base.module'

    def unlink(self):
        raise UserError(_('Records of this model cannot be deleted.'))