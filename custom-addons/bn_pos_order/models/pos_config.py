from odoo import models, _
from odoo.exceptions import AccessError

ARCHIVE_GROUP = 'bn_pos_order.pos_config_archive_group'


class PosConfig(models.Model):
    _inherit = 'pos.config'

    def write(self, vals):
        # archiving or restoring a shop is the Archive group's (also over RPC);
        # a write that leaves the shop as it is needs no right
        if 'active' in vals and not self.env.su and not self.env.user.has_group(ARCHIVE_GROUP):
            if self.filtered(lambda config: config.active != bool(vals['active'])):
                raise AccessError(_('Only users in the "Archive and Unarchived POS Shops" group '
                                    'can archive or restore a shop.'))
        return super().write(vals)
