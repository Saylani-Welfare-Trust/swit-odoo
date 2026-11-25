from odoo import models

POS_GROUP = 'bn_advance_donation.advance_donation_pos_action_group'


class POSSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_product_product(self):
        """Advance Donation products are loaded in the POS of the cashiers of the
        POS Action group only."""
        result = super()._loader_params_product_product()
        result['search_params']['fields'].append('is_advance_donation')
        if not self.env.user.has_group(POS_GROUP):
            domain = result['search_params'].get('domain') or []
            result['search_params']['domain'] = ['&', ('is_advance_donation', '=', False)] + list(domain) \
                if domain else [('is_advance_donation', '=', False)]
        return result
