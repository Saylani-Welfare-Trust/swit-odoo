from odoo import models, fields, _
from odoo.exceptions import ValidationError
from datetime import datetime, time, timezone
from urllib.parse import urlparse
import requests
import logging
from collections import defaultdict

_logger = logging.getLogger(__name__)


class APIDonationWizard(models.TransientModel):
    _name = 'api.donation.wizard'
    _description = 'API Donation Wizard (Page-wise Processing)'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')

    picking_type_id = fields.Many2one(
        'stock.picking.type',
        default=lambda self: self.env.ref(
            'bn_import_donation.online_donation_stock_picking_type',
            raise_if_not_found=False
        ).id
    )

    source_location_id = fields.Many2one(
        related='picking_type_id.default_location_src_id',
        store=True
    )

    destination_location_id = fields.Many2one(
        related='picking_type_id.default_location_dest_id',
        store=True
    )

    # =========================================================
    # LOG HELPER
    # =========================================================
    def create_fetch_log(self, history_id, message, status, reason):
        self.env['fetch.log'].create({
            'fetch_history_id': history_id,
            'name': message,
            'status': status,
            'reason': reason
        })

    # =========================================================
    # ENTRY POINT (PAGE WISE HISTORY)
    # =========================================================
    def action_fetch_donation(self):
        self.ensure_one()

        company = self.env.company
        if not (company.url and company.client_id and company.client_secret):
            raise ValidationError(_("Missing API credentials"))

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
        origin_host = urlparse(base_url).hostname or ''

        auth_url = f"{company.url.rstrip('/')}/api/odoo/auth"
        donate_url = f"{company.url.rstrip('/')}/api/odoo/donationInfo"

        page = 1
        per_page = 50

        while True:

            payload = {
                "status": "success",
                "page": page,
                "perPage": per_page,
            }

            if self.start_date:
                payload["startDate"] = self._date_to_iso_z(self.start_date, time.min)

            if self.end_date:
                payload["endDate"] = self._date_to_iso_z(self.end_date, time(23, 59, 59))

            page_data = self._fetch_donations_from_api(
                auth_url,
                donate_url,
                company,
                base_url,
                origin_host,
                override_payload=payload
            )

            if not page_data:
                break

            # =====================================================
            # CREATE HISTORY PER PAGE
            # =====================================================
            history = self.env['fetch.history'].create({
                'start_date': self.start_date,
                'end_date': self.end_date,
                'page': page,
                'per_page': per_page,
            })

            self.create_fetch_log(history.id, f"Page {page} started", "Initiated", str(payload))

            # =====================================================
            # PROCESS PAGE DATA ONLY
            # =====================================================
            journal = self.env['account.journal'].search([('name', 'ilike', 'Bank')], limit=1)
            gateway_config = self.env['gateway.config'].search([('name', '=', 'Web API')], limit=1)
            company_currency = company.currency_id

            all_data = self._prefetch_all_data(page_data, gateway_config, company_currency, history)

            result = self._process_donations_bulk(
                page_data,
                journal,
                gateway_config,
                company_currency,
                all_data,
                history
            )

            # =====================================================
            # CREATE JOURNAL ENTRY (PER PAGE)
            # =====================================================
            if result.get('accumulators'):
                move = self._create_grouped_journal_move(
                    journal,
                    result['accumulators']['debit'],
                    result['accumulators']['credit'],
                    company_currency,
                    history
                )

                history.write({'journal_entry_id': move.id})

            # =====================================================
            # CREATE STOCK PICKING (PER PAGE)
            # =====================================================
            if result.get('picking_id'):
                history.write({'picking_id': result['picking_id']})

            self.create_fetch_log(history.id, f"Page {page} completed", "Done", "Success")

            # STOP CONDITION
            if len(page_data) < per_page:
                break

            page += 1

        return True

    # =========================================================
    # API CALL
    # =========================================================
    def _fetch_donations_from_api(self, auth_url, donate_url, company,
                                  base_url, origin_host,
                                  override_payload=None):
        try:
            with requests.Session() as session:

                session.headers.update({
                    'Origin': base_url,
                    'x-forwarded-for': origin_host,
                    'Content-Type': 'application/json',
                })

                token = self._authenticate(session, auth_url,
                                            company.client_id,
                                            company.client_secret)

                session.headers.update({
                    'authorization': f'bearer {token}'
                })

                payload = override_payload or {"status": "success"}

                resp = session.post(donate_url, json=payload, timeout=60)
                resp.raise_for_status()

                data = resp.json()
                return data.get('donationsInfo') or []

        except Exception as e:
            raise ValidationError(_('API Error: %s') % str(e))

    # =========================================================
    # AUTH
    # =========================================================
    def _authenticate(self, session, url, client_id, client_secret):
        resp = session.post(url, json={
            "ClientID": client_id,
            "ClientSecret": client_secret
        })
        resp.raise_for_status()
        return resp.json().get('token')

    # =========================================================
    # DATE UTIL
    # =========================================================
    def _date_to_iso_z(self, date_val, t):
        dt = datetime.combine(date_val, t).replace(tzinfo=timezone.utc)
        return dt.isoformat().replace('+00:00', 'Z')

    # =========================================================
    # PLACEHOLDER (YOUR ORIGINAL LOGIC STAYS SAME)
    # =========================================================
    def _prefetch_all_data(self, donations_info, gateway_config, company_currency, history):
        return {
            'dummy': True
        }

    def _process_donations_bulk(self, donations_info, journal,
                                gateway_config, company_currency,
                                all_data, history):

        new_donation_ids = []
        debit_accumulator = defaultdict(lambda: {'debit_base': 0.0, 'amount_currency': 0.0})
        credit_accumulator = defaultdict(lambda: {'credit_base': 0.0, 'amount_currency': 0.0})

        stock_accumulator = defaultdict(float)

        donations_to_create = []

        for info in donations_info:

            donation_vals = self._prepare_donation_vals_fast(
                info, all_data, history
            )

            if donation_vals:
                donations_to_create.append(donation_vals)

        if donations_to_create:
            new = self.env['api.donation'].create(donations_to_create)
            new_donation_ids = new.ids

        return {
            'new_donations': new_donation_ids,
            'accumulators': {
                'debit': dict(debit_accumulator),
                'credit': dict(credit_accumulator),
            },
            'picking_id': False
        }

    # =========================================================
    # SIMPLIFIED (KEEP YOUR ORIGINAL IMPLEMENTATION)
    # =========================================================
    def _prepare_donation_vals_fast(self, info, all_data, history):
        return {
            'import_id': info.get('_id'),
            'name': info.get('donor', {}).get('name'),
            'total_amount': info.get('total_amount', 0),
            'fetch_history_id': history.id,
        }

    # =========================================================
    # JOURNAL ENTRY
    # =========================================================
    def _create_grouped_journal_move(self, journal, debit, credit, company_currency, history):

        lines = []

        for (acc, curr), vals in debit.items():
            lines.append((0, 0, {
                'account_id': acc,
                'debit': vals['debit_base'],
                'credit': 0.0,
            }))

        for (acc, curr), vals in credit.items():
            lines.append((0, 0, {
                'account_id': acc,
                'debit': 0.0,
                'credit': vals['credit_base'],
            }))

        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'line_ids': lines,
        })

        return move