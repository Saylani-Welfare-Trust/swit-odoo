from odoo import models
from odoo.exceptions import ValidationError


class POSConfig(models.Model):
    _inherit = 'pos.config'


    def open_ui(self):
        # raise ValidationError(str(self.env['pos.session'].search([('config_id', '=', self.id), ('state', '=', 'closed')], limit=1).name))

        if self.env['pos.session'].search([('config_id', '=', self.id), ('state', '=', 'closed')], limit=1).move_id.state == 'draft':
            raise ValidationError('Please communicate to your friendly administrator and post the previous session Journal Entry.')
        
        return super(POSConfig, self).open_ui()
