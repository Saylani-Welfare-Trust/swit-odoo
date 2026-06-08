from odoo import models, fields, _
from odoo.exceptions import ValidationError
import logging
import json
from datetime import datetime

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

        domain = [('qurbani', '=', True)]
        if self.start_date:
            domain.append(('created_at', '>=', f"{self.start_date} 00:00:00"))
        if self.end_date:
            domain.append(('created_at', '<=', f"{self.end_date} 23:59:59"))

        donations_info = self.env['api.donation'].search(domain)

        if not donations_info:
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

        # ── Single savepoint: ALL donations succeed or ALL roll back ──────────
        try:
            with self.env.cr.savepoint():
                created_count = 0

                for info in donations_info:
                    donation_dict = info.read()[0]
                    # Any ValidationError raised inside bubbles up immediately,
                    # triggering savepoint rollback for every record processed so far.
                    result = self.env['qurbani.order'].create_web_qurbani_order(
                        donation_dict, donation_name=info.name
                    )
                    created_count += 1
                    self.env['fetch.qurbani.log'].create({
                        'name': f"✓ SUCCESS - Qurbani Order {result.get('name')} | Donation: {info.name} (ID: {info.id})",
                        'status': 'Success',
                        'reason': f"Qurbani Order ID: {result.get('qurbani_order_id')}"
                    })

            # Only reached if ALL succeeded
            summary_msg = f"All {created_count} donations processed successfully."
            self.env['fetch.qurbani.log'].create({
                'name': "SUMMARY: All donations processed",
                'status': 'Summary',
                'reason': summary_msg
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Processing Complete',
                    'message': summary_msg,
                    'type': 'success',
                    'sticky': False,
                }
            }

        except ValidationError as e:
            # Savepoint already rolled back everything — just re-raise so
            # Odoo shows the error dialog to the user. Nothing was committed.
            raise
        except Exception as e:
            _logger.error("Unexpected error during qurbani fetch", exc_info=True)
            raise ValidationError(
                f"Unexpected error during processing — all changes have been rolled back.\n\n{str(e)}"
            )