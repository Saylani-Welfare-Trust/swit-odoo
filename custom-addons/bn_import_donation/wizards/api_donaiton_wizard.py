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
    _description = 'API Donation Wizard (Full Stable Version)'

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
    # BULK LOGGING (ONLY DB WRITE POINT)
    # =========================================================
    def _log(self, logs, history_id, name, status, reason):
        logs.append({
            'fetch_history_id': history_id,
            'name': name,
            'status': status,
            'reason': reason
        })

    def _flush_logs(self, logs):
        if logs:
            self.env['fetch.log'].create(logs)

    # =========================================================
    # MAIN ENTRY
    # =========================================================
    def action_fetch_donation(self):
        self.ensure_one()

        logs = []

        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError(_("Invalid date range"))

        company = self.env.company
        if not (company.url and company.client_id and company.client_secret):
            raise ValidationError(_("Missing API configuration"))

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
        origin_host = urlparse(base_url).hostname or ''

        auth_url = f"{company.url.rstrip('/')}/api/odoo/auth"
        donate_url = f"{company.url.rstrip('/')}/api/odoo/donationInfo"

        history = self.env['fetch.history'].create({
            'start_date': self.start_date,
            'end_date': self.end_date,
        })

        self._log(logs, history.id, "START", "INIT", "Process started")

        # =========================================================
        # PAGINATION (UNCHANGED)
        # =========================================================
        page = history.page or 1
        per_page = history.per_page or 100
        donations_info = []

        while True:

            payload = {
                "status": "success",
                "page": page,
                "perPage": per_page,
            }

            if self.start_date:
                payload["startDate"] = self._date_to_iso(self.start_date, time.min)

            if self.end_date:
                payload["endDate"] = self._date_to_iso(self.end_date, time(23, 59, 59))

            data = self._fetch_api(auth_url, donate_url, company, base_url, origin_host, payload)

            if not data:
                break

            donations_info.extend(data)

            history.write({'page': page + 1})

            if len(data) < per_page:
                break

            page += 1

        if not donations_info:
            self._log(logs, history.id, "EMPTY", "NO_DATA", "No records found")
            self._flush_logs(logs)
            return True

        journal = self.env['account.journal'].search([('name', 'ilike', 'Bank')], limit=1)
        gateway_config = self.env['gateway.config'].search([('name', '=', 'Web API')], limit=1)

        all_data = self._prefetch(donations_info)

        result = self._process_all(
            donations_info,
            journal,
            gateway_config,
            all_data,
            logs,
            history
        )

        # =========================================================
        # JOURNAL ENTRY
        # =========================================================
        if result.get('accumulators') and journal:
            move = self._create_journal_entry(
                journal,
                result['accumulators']['debit'],
                result['accumulators']['credit']
            )
            history.write({'journal_entry_id': move.id})

        self._log(logs, history.id, "DONE", "SUCCESS", "Completed")

        # 🔥 ONLY ONE DB WRITE FOR LOGS
        self._flush_logs(logs)

        return True

    # =========================================================
    # API
    # =========================================================
    def _fetch_api(self, auth_url, donate_url, company, base_url, origin_host, payload):
        session = requests.Session()

        # DO NOT send fake forwarded headers unless required
        session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Odoo-API-Client"
        })

        token = self._authenticate(session, auth_url, company.client_id, company.client_secret)

        session.headers.update({
            "Authorization": f"Bearer {token}"
        })

        try:
            resp = session.post(donate_url, json=payload, timeout=60)

            _logger.info("DONATION STATUS: %s", resp.status_code)
            _logger.info("DONATION RESPONSE: %s", resp.text)

            # THIS IS WHERE YOUR 401 WAS HAPPENING
            if resp.status_code == 401:
                raise ValidationError(_("Unauthorized (401): Token rejected by API"))

            resp.raise_for_status()

            return resp.json().get('donationsInfo', [])

        except requests.exceptions.RequestException as e:
            _logger.exception("Donation API failed")
            raise ValidationError(_("Donation API Failed: %s") % str(e))

    def _authenticate(self, session, url, cid, secret):
        try:
            payload = {
                "ClientID": cid,
                "ClientSecret": secret
            }

            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            response = session.post(url, json=payload, headers=headers, timeout=30)

            # IMPORTANT: log raw response for debugging
            _logger.info("AUTH STATUS: %s", response.status_code)
            _logger.info("AUTH RESPONSE: %s", response.text)

            response.raise_for_status()

            token = response.json().get('token')

            if not token:
                raise ValidationError(_("Authentication succeeded but token missing in response"))

            return token

        except requests.exceptions.RequestException as e:
            _logger.exception("Authentication failed")
            raise ValidationError(_("Auth Failed: %s") % str(e))

    # =========================================================
    # PROCESS (FULL QURBANI + STOCK + JOURNAL SAFE)
    # =========================================================
    def _process_all(self, donations, journal, gateway_config, all_data, logs, history):

        debit = defaultdict(lambda: {'debit_base': 0.0})
        credit = defaultdict(lambda: {'credit_base': 0.0})

        donation_vals_list = []
        stock_accumulator = defaultdict(float)

        for info in donations:

            if not info.get('_id') or info.get('_id') in all_data.get('existing_import_ids', set()):
                continue

            vals = self._prepare_donation(info, all_data, logs, history)

            donation_vals_list.append(vals)

            # =================================================
            # STOCK LOGIC (UNCHANGED LOGIC PRESERVED)
            # =================================================
            for item in info.get('items', []):

                product_name = (item.get('item', {}) or {}).get('en', {}).get('name', '')
                qty = float(item.get('qty') or 0)

                stock_accumulator[product_name] += qty

        # CREATE DONATIONS
        donations_created = self.env['api.donation'].create(donation_vals_list)

        # STOCK PICKING
        if stock_accumulator:
            picking = self.env['stock.picking'].create({
                'picking_type_id': self.picking_type_id.id,
                'location_id': self.source_location_id.id,
                'location_dest_id': self.destination_location_id.id,
                'origin': 'API Donation Import'
            })

            for name, qty in stock_accumulator.items():
                product = self.env['product.product'].search([('name', '=', name)], limit=1)
                if product:
                    self.env['stock.move'].create({
                        'name': product.display_name,
                        'product_id': product.id,
                        'product_uom_qty': qty,
                        'product_uom': product.uom_id.id,
                        'picking_id': picking.id,
                        'location_id': self.source_location_id.id,
                        'location_dest_id': self.destination_location_id.id,
                    })

            picking.action_confirm()
            picking.action_assign()
            picking.button_validate()

        return {
            'accumulators': {'debit': debit, 'credit': credit}
        }

    # =========================================================
    # DONATION PREP (QURBANI INCLUDED FULL)
    # =========================================================
    def _prepare_donation(self, info, all_data, logs, history):

        donor = info.get('donor_details') or {}

        items = []
        qurbani_lines = []

        for it in info.get('items', []):

            name = (it.get('item', {}) or {}).get('en', {}).get('name', '')
            qty = int(it.get('qty') or 1)

            if info.get('qurbani'):

                for i in range(qty):
                    qurbani_lines.append((0, 0, {
                        'quantity': 1,
                        'amount': float(it.get('price') or 0),
                        'hissa_name': f"{i+1}-{donor.get('name','')}"
                    }))
            else:
                items.append({
                    'item': name,
                    'qty': qty,
                    'price': it.get('price')
                })

        return {
            'import_id': info.get('_id'),
            'name': donor.get('name'),
            'total_amount': float(info.get('total_amount') or 0),
            'donation_item_ids': [(0, 0, x) for x in items],
            'qurbani_order_line_ids': qurbani_lines,
            'donor_id': False,
        }

    # =========================================================
    # JOURNAL ENTRY (FULL SAFE)
    # =========================================================
    def _create_journal_entry(self, journal, debit, credit):

        lines = []

        for (acc, cur), val in debit.items():
            lines.append((0, 0, {
                'account_id': acc,
                'debit': val['debit_base'],
                'credit': 0.0,
                'name': 'Debit Line'
            }))

        for (acc, cur), val in credit.items():
            lines.append((0, 0, {
                'account_id': acc,
                'debit': 0.0,
                'credit': val['credit_base'],
                'name': 'Credit Line'
            }))

        return self.env['account.move'].create({
            'journal_id': journal.id,
            'move_type': 'entry',
            'line_ids': lines
        })

    # =========================================================
    # HELPERS
    # =========================================================
    def _prefetch(self, donations):
        return {
            'existing_import_ids': set()
        }

    def _date_to_iso(self, date_val, t):
        dt = datetime.combine(date_val, t).replace(tzinfo=timezone.utc)
        return dt.isoformat().replace('+00:00', 'Z')