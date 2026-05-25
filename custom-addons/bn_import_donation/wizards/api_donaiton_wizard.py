from odoo import models, fields, _
from odoo.exceptions import ValidationError
from datetime import datetime, time, timezone
from collections import defaultdict
import requests
import logging

_logger = logging.getLogger(__name__)


class APIDonationWizard(models.TransientModel):
    _name = 'api.donation.wizard'
    _description = 'API Donation Wizard'

    # =========================================================
    # FIELDS
    # =========================================================

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
    # LOGGER
    # =========================================================

    def log_batch(self, history, logs):
        if not logs:
            return

        self.env['fetch.log'].sudo().create([
            {
                'fetch_history_id': history.id,
                'name': (log.get('name') or '')[:500],
                'status': log.get('status', 'info'),
                'reason': (log.get('reason') or '')[:3000],
            }
            for log in logs
        ])

    # =========================================================
    # MAIN ENTRY
    # =========================================================

    def action_fetch_donation(self):
        self.ensure_one()

        logs = []

        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValidationError(_("Start Date must be earlier than End Date."))

        company = self.env.company

        history = self.env['fetch.history'].create({
            'start_date': self.start_date,
            'end_date': self.end_date,
            'page': 1,
            'per_page': 100,
            'state': 'in_progress',
        })

        try:
            logs.append({'name': 'Donation import started', 'status': 'info'})

            payload = {"status": "success", "page": 1, "perPage": 100}

            if self.start_date:
                payload['startDate'] = self._date_to_iso_z(self.start_date, time.min)

            if self.end_date:
                payload['endDate'] = self._date_to_iso_z(self.end_date, time(23, 59, 59))

            donations = self._fetch_donations_from_api(company, payload)

            if not donations:
                history.write({'state': 'completed'})
                self.log_batch(history, logs)
                return True

            journal = self.env['account.journal'].search([('type', '=', 'bank')], limit=1)
            if not journal:
                raise ValidationError(_("No bank journal found."))

            gateway_config = self.env['gateway.config'].search([('name', '=', 'Web API')], limit=1)
            if not gateway_config:
                raise ValidationError(_("Gateway config not found."))

            all_data = self._prefetch_all_data(donations, gateway_config)

            result = self._process_donations_bulk(
                donations, gateway_config, company, all_data, history, logs
            )

            move = self._create_grouped_journal_move(
                journal,
                result['debit_accumulator'],
                result['credit_accumulator'],
                company.currency_id,
                logs
            )

            if move:
                history.write({'journal_entry_id': move.id})

            if result.get('picking_id'):
                history.write({'picking_id': result['picking_id']})

            history.write({'state': 'completed'})

            self.log_batch(history, logs)

            return True

        except Exception as e:
            history.write({'state': 'completed'})
            logs.append({'name': 'Failed', 'status': 'error', 'reason': str(e)})
            self.log_batch(history, logs)
            _logger.exception("Donation Import Failed")
            raise ValidationError(str(e))

    # =========================================================
    # API
    # =========================================================

    def _fetch_donations_from_api(self, company, payload):
        session = requests.Session()

        auth_url = f"{company.url.rstrip('/')}/api/odoo/auth"
        donate_url = f"{company.url.rstrip('/')}/api/odoo/donationInfo"

        auth = session.post(auth_url, json={
            "ClientID": company.client_id,
            "ClientSecret": company.client_secret
        }, timeout=(30, 120))

        token = auth.json().get('token')
        if not token:
            raise ValidationError(_("Auth failed"))

        session.headers.update({'authorization': f'bearer {token}'})

        res = session.post(donate_url, json=payload, timeout=(30, 300))
        res.raise_for_status()

        return res.json().get('donationsInfo', [])

    # =========================================================
    # PREFETCH
    # =========================================================

    def _prefetch_all_data(self, donations, gateway_config):

        currencies = {d.get('currency') for d in donations if d.get('currency')}
        import_ids = {d.get('_id') for d in donations if d.get('_id')}
        mobiles = {d.get('donor_details', {}).get('phone', '')[-10:] for d in donations}

        currency_map = {
            c.name.lower(): c
            for c in self.env['res.currency'].search([('name', 'in', list(currencies))])
        }

        existing_import_ids = set(
            x['import_id']
            for x in self.env['api.donation'].search_read(
                [('import_id', 'in', list(import_ids))], ['import_id']
            )
        )

        partner_map = {
            p['mobile']: p['id']
            for p in self.env['res.partner'].search_read(
                [('mobile', 'in', list(mobiles))], ['mobile']
            )
        }

        gateway_currency_lines = {
            line.currency_id.name.lower(): line.account_id.id
            for line in gateway_config.gateway_config_currency_ids
        }

        gateway_product_lines = {
            (line.name or '').strip().lower(): {
                'product_id': line.product_id.id,
                'account_id': (
                    line.product_id.property_account_income_id.id
                    or line.product_id.categ_id.property_account_income_categ_id.id
                )
            }
            for line in gateway_config.gateway_config_line_ids
        }

        return {
            'currency_map': currency_map,
            'existing_import_ids': existing_import_ids,
            'partner_map': partner_map,
            'gateway_currency_lines': gateway_currency_lines,
            'gateway_product_lines': gateway_product_lines,
        }

    # =========================================================
    # PROCESS
    # =========================================================

    def _process_donations_bulk(self, donations, gateway_config, company, all_data, history, logs):

        donations_vals = []
        debit = defaultdict(float)
        credit = defaultdict(float)
        partner_cache = all_data['partner_map']
        partner_create = []

        for d in donations:

            if d.get('_id') in all_data['existing_import_ids']:
                continue

            if d.get('status') != 'success':
                continue

            donor = d.get('donor_details') or {}
            mobile = donor.get('phone', '')[-10:]

            if mobile and not partner_cache.get(mobile):
                partner_create.append({
                    'name': donor.get('name'),
                    'mobile': mobile,
                    'email': donor.get('email')
                })

            donation_items = []

            for item in d.get('items', []):

                name = ''
                if isinstance(item.get('item'), dict):
                    name = item['item'].get('en', {}).get('name', '')

                donation_items.append((0, 0, {
                    'item': name,
                    'qty': item.get('qty'),
                    'price': item.get('price'),
                    'total': item.get('total'),
                }))

                key = name.strip().lower()
                config = all_data['gateway_product_lines'].get(key)
                if not config:
                    continue

                total = float(item.get('total') or 0)

                debit_acc = all_data['gateway_currency_lines'].get((d.get('currency') or '').lower())
                credit_acc = config['account_id']

                if debit_acc:
                    debit[debit_acc] += total
                if credit_acc:
                    credit[credit_acc] += total

            donations_vals.append({
                'import_id': d.get('_id'),
                'name': donor.get('name'),
                'phone': donor.get('phone'),
                'email': donor.get('email'),
                'donation_item_ids': donation_items,
                'fetch_history_id': history.id,
            })

        self.env['res.partner'].create(partner_create)

        created = self.env['api.donation'].create(donations_vals)

        return {
            'created_donations': created.ids,
            'debit_accumulator': debit,
            'credit_accumulator': credit,
            'picking_id': False
        }

    # =========================================================
    # JOURNAL (FIXED)
    # =========================================================

    def _create_grouped_journal_move(self, journal, debit, credit, currency, logs):

        lines = []

        for acc, amt in debit.items():
            lines.append((0, 0, {
                'account_id': acc,
                'debit': amt,
                'credit': 0.0,
                'currency_id': currency.id,
                'amount_currency': amt,
                'name': 'Donation Debit'
            }))

        for acc, amt in credit.items():
            lines.append((0, 0, {
                'account_id': acc,
                'debit': 0.0,
                'credit': amt,
                'currency_id': currency.id,
                'amount_currency': -amt,
                'name': 'Donation Credit'
            }))

        if not lines:
            return False

        move = self.env['account.move'].create({
            'journal_id': journal.id,
            'move_type': 'entry',
            'line_ids': lines,
        })

        move.action_post()
        return move

    # =========================================================
    # HELPER
    # =========================================================

    def _date_to_iso_z(self, date_val, t):
        return datetime.combine(date_val, t).replace(
            tzinfo=timezone.utc
        ).isoformat(timespec='milliseconds').replace('+00:00', 'Z')