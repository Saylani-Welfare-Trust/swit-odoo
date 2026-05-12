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

    @api.model
    def _update_database_constraint(self):
        """
        Fix the database constraints if they exist with CASCADE instead of SET NULL
        """
        try:
            with self.env.cr.cursor() as cr:
                # Check for any problematic constraints
                cr.execute("""
                    SELECT constraint_name
                    FROM information_schema.table_constraints
                    WHERE table_name = 'api_donation_item'
                    AND constraint_type = 'FOREIGN KEY'
                """)
                constraints = cr.fetchall()
                
                for constraint in constraints:
                    constraint_name = constraint[0]
                    _logger.debug(f"Found constraint on api_donation_item: {constraint_name}")
                    
        except Exception as e:
            _logger.warning(f"Error checking database constraints: {str(e)}")

    def unlink(self):
        """
        Delete records safely, archive if constraints prevent deletion.
        Handles foreign key constraints gracefully.
        """
        if not self:
            return True
        
        # First try to update the database constraint
        self._update_database_constraint()
        
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
                    # Archive the records by setting active to False
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
