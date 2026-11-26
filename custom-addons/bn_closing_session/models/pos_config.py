from odoo import models
from odoo.exceptions import ValidationError


class POSConfig(models.Model):
    _inherit = 'pos.config'


    def open_ui(self):

        # cashiers cannot read journal entries: check the last session's as superuser
        last_closed = self.env['pos.session'].sudo().search(
            [('config_id', '=', self.id), ('state', '=', 'closed')], order='id desc', limit=1)
        if last_closed.move_id.state == 'draft':
            raise ValidationError('Please communicate to your friendly administrator and post the previous session Journal Entry.')
        
        return super(POSConfig, self).open_ui()
