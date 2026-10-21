from odoo import models, _
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    _inherit = 'pos.config'
    
    
    def write(self, vals):
            if vals.get('active') is False:
                if not self.env.user.has_group(
                    'bn_pos_order.pos_config_archive_group'
                ):
                    raise ValidationError(
                        _("Only users in the POS / Archive group can archive a shop.")
                    )
    
            return super().write(vals)