from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class ApiQurbaniOrderLine(models.Model):
    _name = 'api.qurbani.order.line'
    _description = "Api Qurbani Order Line"


    qurbani_order_id = fields.Many2one('api.donation', string="Qurbani Order", ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Product", ondelete='set null')
    city_id = fields.Many2one('stock.location', string="City", ondelete='set null')
    distribution_id = fields.Many2one('stock.location', string="Distribution", ondelete='set null')
    day_id = fields.Many2one('qurbani.day', string="Day", ondelete='set null')
    hijri_id = fields.Many2one('hijri', string="Hijri", ondelete='set null')

    name = fields.Char('Name', default="New")
    hissa_name = fields.Char('Hissa Name')

    start_time = fields.Float('Start Time')
    end_time = fields.Float('End Time')

    quantity = fields.Integer('Quantity', default=1)

    amount = fields.Float('Amount')
    active = fields.Boolean('Active', default=True)

    @api.model
    def _update_database_constraint(self):
        """
        Fix the database constraint to allow SET NULL on product_id deletion
        This handles cases where the database has CASCADE constraint instead of SET NULL
        """
        try:
            with self.env.cr.cursor() as cr:
                # Check if the problematic constraint exists
                cr.execute("""
                    SELECT constraint_name
                    FROM information_schema.table_constraints
                    WHERE table_name = 'api_qurbani_order_line'
                    AND constraint_type = 'FOREIGN KEY'
                    AND constraint_name LIKE '%product_id%'
                """)
                result = cr.fetchone()
                
                if result:
                    constraint_name = result[0]
                    _logger.info(f"Found constraint: {constraint_name}. Attempting to update...")
                    
                    try:
                        # Drop the old constraint
                        cr.execute(f"ALTER TABLE api_qurbani_order_line DROP CONSTRAINT {constraint_name}")
                        
                        # Create new constraint with SET NULL
                        cr.execute("""
                            ALTER TABLE api_qurbani_order_line
                            ADD CONSTRAINT api_qurbani_order_line_product_id_fkey
                            FOREIGN KEY (product_id)
                            REFERENCES product_product (id)
                            ON DELETE SET NULL
                        """)
                        self.env.cr.commit()
                        _logger.info("Successfully updated database constraint to SET NULL")
                    except Exception as e:
                        _logger.warning(f"Could not update constraint: {str(e)}")
        except Exception as e:
            _logger.warning(f"Error checking database constraint: {str(e)}")

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
            return super(ApiQurbaniOrderLine, self).unlink()
        except Exception as e:
            error_msg = str(e).lower()
            
            # If it's a foreign key or constraint violation, archive instead
            if any(keyword in error_msg for keyword in ['foreign key', 'constraint', 'violates', 'fkey']):
                _logger.warning(
                    f"Deletion constraint violation for api.qurbani.order.line records. "
                    f"Archiving {len(self)} records instead. Error: {str(e)}"
                )
                try:
                    # Before archiving, clear the product_id to remove any constraints
                    self.write({'product_id': False, 'active': False})
                    return True
                except Exception as archive_error:
                    _logger.error(f"Failed to archive api.qurbani.order.line: {str(archive_error)}")
                    raise UserError(
                        _("Cannot delete or archive records: %s") % str(archive_error)
                    )
            else:
                # Re-raise if it's not a constraint-related error
                _logger.error(f"Unexpected error deleting api.qurbani.order.line: {str(e)}")
                raise
    
    @api.model
    def delete_or_archive_orphaned_records(self):
        """
        Clean up orphaned api.qurbani.order.line records that don't have:
        - A valid qurbani_order_id (api.donation)
        - A product_id (if required)
        """
        orphaned_records = self.search([
            ('qurbani_order_id', '=', False),
        ])
        
        if orphaned_records:
            try:
                orphaned_records.unlink()
                _logger.info(f"Deleted {len(orphaned_records)} orphaned api.qurbani.order.line records")
            except Exception as e:
                _logger.warning(
                    f"Failed to delete orphaned records, archiving instead: {str(e)}"
                )
                orphaned_records.write({'active': False})
        
        return True
