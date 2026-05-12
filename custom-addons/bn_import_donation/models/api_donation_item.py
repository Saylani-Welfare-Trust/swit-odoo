from odoo import fields, models
import logging

_logger = logging.getLogger(__name__)


class APIDonationItemModel(models.Model):
    _name = 'api.donation.item'
    _description = 'API Donation Item'


    donation_type = fields.Char('Donation Type')
    donation_no = fields.Char('Donation No')
    price_id = fields.Char('Price Id')
    price = fields.Float('Price')
    total = fields.Float('Total')
    type = fields.Char('Type')
    item = fields.Char('Item')
    qty = fields.Float('QTY')
    
    is_priced_item = fields.Boolean('Is Priced Item')

    api_donation_id = fields.Many2one('api.donation', string='Donation Data', ondelete='cascade')
    active = fields.Boolean('Active', default=True)

    def unlink(self):
        """Archive instead of hard delete to avoid constraint violations"""
        try:
            return super().unlink()
        except Exception as e:
            # If deletion fails due to constraints, archive instead
            _logger.warning(f"Deletion failed for api.donation.item, archiving instead: {str(e)}")
            self.write({'active': False})
            return True
