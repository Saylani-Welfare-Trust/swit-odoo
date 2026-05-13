from odoo import models, fields, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class APIDonationWizard(models.TransientModel):
    _name = 'api.qurbani.wizard'
    _description = 'API Qurbani Wizard (refactored)'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')


    def create_fetch_log(self, message, status, reason):
        """Helper to create fetch log entries"""
        self.env['fetch.qurbani.log'].create({
            'name': message,
            'status': status,
            'reason': reason
        })

    # ---------------------- Public entry point ----------------------
    def action_fetch_qurbani(self):
        self.ensure_one()

        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError(_("Start Date must be earlier than or equal to End Date."))

        self.create_fetch_log(f"Start action_fetch_qurbani", 'API Fetch', 'Starting fetch Qurbani donations from donation inflows')
        
        # Build search domain
        domain = [('qurbani', '=', True)]
        
        # Handle date range filtering (created_at is a Datetime field)
        if self.start_date:
            # Convert date to datetime at start of day
            start_datetime = f"{self.start_date} 00:00:00"
            domain.append(('created_at', '>=', start_datetime))
        
        if self.end_date:
            # Convert date to datetime at end of day
            end_datetime = f"{self.end_date} 23:59:59"
            domain.append(('created_at', '<=', end_datetime))
        
        # Fetch ALL matching donations (remove limit=1)
        donations_info = self.env['api.donation'].search(domain)
        
        if not donations_info:
            self.create_fetch_log(f"No qurbani donations found for the given date range", 'Info', 'Search returned no results')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Info',
                    'message': 'No qurbani donations found for the given date range',
                    'type': 'info',
                    'sticky': False,
                }
            }
        
        self.create_fetch_log(f"Found {len(donations_info)} qurbani donations to process", 'API Fetch', f"Processing {len(donations_info)} donations")
        
        created_count = 0
        failed_count = 0
        results = []
        
        for info in donations_info:
            try:
                # Convert Odoo record to dictionary
                donation_dict = info.read()[0]
                
                # Create qurbani order from donation
                # raise ValidationError(str(donation_dict))
                result = self.env['qurbani.order'].create_web_qurbani_order(donation_dict)
                
                if result.get('status') == 'success':
                    created_count += 1
                    self.create_fetch_log(
                        f"Successfully created Qurbani Order {result.get('name')} for donation {info.name}",
                        'Success',
                        f"Qurbani Order ID: {result.get('qurbani_order_id')}"
                    )
                    results.append(result)
                else:
                    failed_count += 1
                    error_msg = result.get('message', 'Unknown error')
                    self.create_fetch_log(
                        f"Failed to create order for donation {info.name}: {error_msg}",
                        'Error',
                        f"Error details: {error_msg}"
                    )
                    
            except Exception as e:
                raise ValidationError(f"Error processing donation {info.read()}: {str(e)}")
                failed_count += 1
                self.create_fetch_log(
                    f"Error processing donation {info.name}: {str(e)}",
                    'Error',
                    f"Exception: {str(e)}"
                )
                _logger.exception(f"Error processing donation {info.id}")
                continue
        
        # Return summary notification
        summary_msg = f"Processed {len(donations_info)} donations: {created_count} succeeded, {failed_count} failed"
        self.create_fetch_log(f"End action_fetch_qurbani", 'API Fetch', summary_msg)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Processing Complete',
                'message': summary_msg,
                'type': 'success' if failed_count == 0 else 'warning',
                'sticky': False,
            }
        }