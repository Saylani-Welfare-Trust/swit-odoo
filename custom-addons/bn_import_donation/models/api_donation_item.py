from odoo import fields, models, api, _
from odoo.exceptions import UserError
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
        """
        Delete records safely, archive if constraints prevent deletion.
        Handles foreign key constraints gracefully.
        """
        if not self:
            return True
        
        # First try normal deletion
        try:
            return super(APIDonationItemModel, self).unlink()
        except Exception as e:
            error_msg = str(e).lower()
            
            # If it's a foreign key or constraint violation, archive instead
            if any(keyword in error_msg for keyword in ['foreign key', 'constraint', 'violates', 'fkey']):
                _logger.warning(
                    f"Deletion constraint violation for api.donation.item records. "
                    f"Archiving {len(self)} records instead. Error: {str(e)}"
                )
                try:
                    self.write({'active': False})
                    return True
                except Exception as archive_error:
                    _logger.error(f"Failed to archive api.donation.item: {str(archive_error)}")
                    raise UserError(
                        _("Cannot delete or archive records: %s") % str(archive_error)
                    )
            else:
                # Re-raise if it's not a constraint-related error
                _logger.error(f"Unexpected error deleting api.donation.item: {str(e)}")
                raise
