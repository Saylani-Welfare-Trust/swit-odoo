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
    _description = 'API Donation Wizard (Production)'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')

    picking_type_id = fields.Many2one(
        'stock.picking.type',
        string="Picking Type",
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
    def create_fetch_log(self, history_id, message, status='Info', reason=''):
        self.env['fetch.log'].create({
            'fetch_history_id': history_id,
            'name': message,
            'status': status,
            'reason': reason
        })

    # =========================================================
    # ENTRY POINT
    # =========================================================
    def action_fetch_donation(self):
        self.ensure_one()

        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError(_("Start Date must be earlier than End Date."))

        company = self.env.company
        if not (company.url and company.client_id and company.client_secret):
            raise ValidationError(_("Missing API configuration."))

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
        origin_host = urlparse(base_url).hostname or ''

        auth_url = f"{company.url.rstrip('/')}/api/odoo/auth"
        donate_url = f"{company.url.rstrip('/')}/api/odoo/donationInfo"

        history = self.env['fetch.history'].create({
            'start_date': self.start_date,
            'end_date': self.end_date,
        })

        self.create_fetch_log(history.id, "Donation fetch started", "Started")

        donations_info = self._fetch_donations_from_api(
            auth_url, donate_url, company, base_url, origin_host, history
        )

        if not donations_info:
            self.create_fetch_log(history.id, "No data found", "Empty")
            return True

        journal = self.env['account.journal'].search([('name', 'ilike', 'Bank')], limit=1)
        gateway_config = self.env['gateway.config'].search([('name', '=', 'Web API')], limit=1)

        all_data = self._prefetch_all_data(donations_info, gateway_config, history)

        result = self._process_donations_bulk(
            donations_info, journal, gateway_config, all_data, history
        )

        if result.get('new_donations') and result.get('accumulators'):
            move = self._create_grouped_journal_move(
                journal,
                result['accumulators']['debit'],
                result['accumulators']['credit'],
                history
            )

            history.write({
                'journal_entry_id': move.id,
                'picking_id': result.get('picking_id')
            })

        self.create_fetch_log(history.id, "Completed successfully", "Done")
        return True

    # =========================================================
    # API FETCH
    # =========================================================
    def _fetch_donations_from_api(self, auth_url, donate_url, company, base_url, origin_host, history):
        with requests.Session() as session:
            session.headers.update({
                'Origin': base_url,
                'x-forwarded-for': origin_host,
                'Content-Type': 'application/json',
            })

            token = self._authenticate(session, auth_url, company)
            session.headers.update({'authorization': f'bearer {token}'})

            payload = {'status': 'success'}
            if self.start_date:
                payload['startDate'] = self._date_to_iso_z(self.start_date)
            if self.end_date:
                payload['endDate'] = self._date_to_iso_z(self.end_date)

            resp = session.post(donate_url, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()

            return data.get('donationsInfo') or []

    def _authenticate(self, session, url, company):
        resp = session.post(url, json={
            "ClientID": company.client_id,
            "ClientSecret": company.client_secret
        }, timeout=30)

        resp.raise_for_status()
        token = resp.json().get('token')

        if not token:
            raise ValidationError(_("Auth token missing"))

        return token

    # =========================================================
    # PREFETCH
    # =========================================================
    def _prefetch_all_data(self, donations_info, gateway_config, history):
        currencies = {d.get('currency') for d in donations_info if d.get('currency')}
        countries = {d.get('donor_details', {}).get('country') for d in donations_info}

        currency_recs = self.env['res.currency'].search([('name', 'in', list(currencies))])
        country_recs = self.env['res.country'].search([('code', 'in', list(countries))])

        return {
            'currency_by_name': {c.name.lower(): c for c in currency_recs},
            'country_by_code': {c.code: c.id for c in country_recs},
        }

    # =========================================================
    # PROCESS BULK
    # =========================================================
    def _process_donations_bulk(self, donations_info, journal, gateway_config, all_data, history):

        new_donation_ids = []
        debit_acc = defaultdict(lambda: 0.0)
        credit_acc = defaultdict(lambda: 0.0)

        StockPicking = self.env['stock.picking']
        StockMove = self.env['stock.move']
        stock_acc = defaultdict(float)

        partner_map = {}
        donations_to_create = []

        for info in donations_info:

            if info.get('status') != 'success':
                continue

            import_id = info.get('_id')
            if not import_id:
                continue

            donor = info.get('donor_details') or {}

            donation_vals = {
                'import_id': import_id,
                'total_amount': float(info.get('total_amount', 0)),
                'currency': info.get('currency'),
                'remarks': info.get('remarks'),
                'name': donor.get('name'),
                'phone': donor.get('phone'),
                'email': donor.get('email'),
                'donation_item_ids': [(0, 0, it) for it in (info.get('items') or [])],
            }

            donations_to_create.append(donation_vals)

            # STOCK ACCUMULATION
            for it in info.get('items') or []:
                product_name = it.get('item', {}).get('en', {}).get('name', '')
                product_line = gateway_config.gateway_config_line_ids.filtered(
                    lambda l: (l.name or '').lower() == product_name.lower()
                )
                product = product_line.product_id if product_line else False

                if product and product.detailed_type == 'product':
                    stock_acc[product.id] += float(it.get('qty', 1))

        # CREATE DONATIONS
        new_records = self.env['api.donation'].create(donations_to_create)
        new_donation_ids = new_records.ids

        # STOCK PICKING
        picking_id = False
        if stock_acc:
            picking = StockPicking.create({
                'picking_type_id': self.picking_type_id.id,
                'location_id': self.source_location_id.id,
                'location_dest_id': self.destination_location_id.id,
                'origin': 'API Donation Import',
            })

            for product_id, qty in stock_acc.items():
                product = self.env['product.product'].browse(product_id)

                StockMove.create({
                    'name': product.display_name,
                    'product_id': product.id,
                    'product_uom_qty': qty,
                    'quantity': qty,
                    'product_uom': product.uom_id.id,
                    'picking_id': picking.id,
                    'location_id': self.source_location_id.id,
                    'location_dest_id': self.destination_location_id.id,
                })

            picking.action_confirm()
            picking.action_assign()
            picking.button_validate()
            picking_id = picking.id

        return {
            'new_donations': new_donation_ids,
            'accumulators': {
                'debit': debit_acc,
                'credit': credit_acc
            },
            'picking_id': picking_id
        }

    # =========================================================
    # JOURNAL ENTRY
    # =========================================================
    def _create_grouped_journal_move(self, journal, debit_acc, credit_acc, history):

        lines = []

        for (account_id, currency_id), amount in debit_acc.items():
            if amount:
                lines.append((0, 0, {
                    'account_id': account_id,
                    'debit': amount,
                    'credit': 0.0,
                    'name': 'Donation Debit'
                }))

        for (account_id, currency_id), amount in credit_acc.items():
            if amount:
                lines.append((0, 0, {
                    'account_id': account_id,
                    'debit': 0.0,
                    'credit': amount,
                    'name': 'Donation Credit'
                }))

        move = self.env['account.move'].sudo().create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': fields.Date.today(),
            'ref': 'Donation Import',
            'line_ids': lines
        })

        return move

    # =========================================================
    # HELPERS
    # =========================================================
    def _date_to_iso_z(self, date_val):
        dt = datetime.combine(date_val, time.min).replace(tzinfo=timezone.utc)
        return dt.isoformat().replace('+00:00', 'Z')