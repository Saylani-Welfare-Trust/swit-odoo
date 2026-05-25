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
    # BULK LOGGER
    # =========================================================

    def log_batch(self, history, logs):

        if not logs:
            return

        vals_list = []

        for log in logs:
            vals_list.append({
                'fetch_history_id': history.id,
                'name': (log.get('name') or '')[:500],
                'status': log.get('status', 'info'),
                'reason': (log.get('reason') or '')[:3000],
            })

        self.env['fetch.log'].sudo().create(vals_list)

    # =========================================================
    # MAIN ENTRY
    # =========================================================

    def action_fetch_donation(self):

        self.ensure_one()

        logs = []

        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValidationError(
                    _("Start Date must be earlier than End Date.")
                )

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

            payload = {
                "status": "success",
                "page": 1,
                "perPage": 100,
            }

            if self.start_date:
                payload['startDate'] = self._date_to_iso_z(self.start_date, time.min)

            if self.end_date:
                payload['endDate'] = self._date_to_iso_z(self.end_date, time(23, 59, 59))

            donations = self._fetch_donations_from_api(company, payload, logs)

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

            all_data = self._prefetch_all_data(donations, gateway_config, company, logs)

            result = self._process_donations_bulk(
                donations, journal, gateway_config, company, all_data, history, logs
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
            self.log_batch(history, logs)
            _logger.exception("Donation Import Failed")
            raise ValidationError(str(e))

    # =========================================================
    # FETCH API
    # =========================================================

    def _fetch_donations_from_api(self, company, payload, logs):

        session = requests.Session()

        auth_url = f"{company.url.rstrip('/')}/api/odoo/auth"
        donate_url = f"{company.url.rstrip('/')}/api/odoo/donationInfo"

        auth_response = session.post(
            auth_url,
            json={"ClientID": company.client_id, "ClientSecret": company.client_secret},
            timeout=(30, 120)
        )

        token = auth_response.json().get('token')
        if not token:
            raise ValidationError(_("Authentication token missing"))

        session.headers.update({'authorization': f'bearer {token}'})

        response = session.post(donate_url, json=payload, timeout=(30, 300))
        response.raise_for_status()

        return response.json().get('donationsInfo', [])

    # =========================================================
    # PREFETCH
    # =========================================================

    def _prefetch_all_data(self, donations, gateway_config, company, logs):

        currencies = set()
        import_ids = set()
        mobiles = set()

        for d in donations:
            if d.get('currency'):
                currencies.add(d['currency'])
            if d.get('_id'):
                import_ids.add(d['_id'])
            if d.get('donor_details', {}).get('phone'):
                mobiles.add(d['donor_details']['phone'][-10:])

        currency_map = {
            c.name.lower(): c
            for c in self.env['res.currency'].search([('name', 'in', list(currencies))])
        }

        existing_import_ids = set(
            x['import_id']
            for x in self.env['api.donation'].search_read(
                [('import_id', 'in', list(import_ids))],
                ['import_id']
            )
        )

        partner_map = {
            p['mobile']: p['id']
            for p in self.env['res.partner'].search_read(
                [('mobile', 'in', list(mobiles))],
                ['mobile']
            )
        }

        gateway_currency_lines = {
            line.currency_id.name.lower(): line.account_id.id
            for line in gateway_config.gateway_config_currency_ids
            if line.currency_id and line.account_id
        }

        gateway_product_lines = {}

        for line in gateway_config.gateway_config_line_ids:
            key = (line.name or '').strip().lower()
            account_id = (
                line.product_id.property_account_income_id.id
                or line.product_id.categ_id.property_account_income_categ_id.id
            )
            gateway_product_lines[key] = {
                'product_id': line.product_id.id,
                'account_id': account_id,
            }

        return {
            'currency_map': currency_map,
            'existing_import_ids': existing_import_ids,
            'partner_map': partner_map,
            'gateway_currency_lines': gateway_currency_lines,
            'gateway_product_lines': gateway_product_lines,
        }

    # =========================================================
    # PROCESS DONATIONS
    # =========================================================

    def _process_donations_bulk(self, donations, journal, gateway_config, company, all_data, history, logs):

        donations_vals = []
        debit_accumulator = defaultdict(float)
        credit_accumulator = defaultdict(float)
        stock_accumulator = defaultdict(float)
        partner_cache = all_data['partner_map']
        partner_create_vals = []

        for donation in donations:

            if donation.get('_id') in all_data['existing_import_ids']:
                continue

            if donation.get('status') != 'success':
                continue

            donor = donation.get('donor_details') or {}
            mobile = donor.get('phone', '')[-10:]
            partner_id = partner_cache.get(mobile)

            if not partner_id and mobile:
                partner_create_vals.append({
                    'name': donor.get('name'),
                    'mobile': mobile,
                    'email': donor.get('email'),
                })

            currency_name = (donation.get('currency') or '').lower()

            donation_vals = {
                'import_id': donation.get('_id'),
                'name': donor.get('name'),
                'phone': donor.get('phone'),
                'email': donor.get('email'),
                'currency': currency_name,
                'total_amount': float(donation.get('total_amount', 0)),
                'fetch_history_id': history.id,
            }

            if partner_id:
                donation_vals['donor_id'] = partner_id

            donation_items = []

            for item in donation.get('items', []):

                item_name = ''
                if isinstance(item.get('item'), dict):
                    item_name = item['item'].get('en', {}).get('name', '')

                donation_items.append((0, 0, {
                    'item': item_name,
                    'qty': item.get('qty'),
                    'price': item.get('price'),
                    'total': item.get('total'),
                }))

                product_key = item_name.strip().lower()
                config = all_data['gateway_product_lines'].get(product_key)
                if not config:
                    continue

                total = float(item.get('total') or 0)

                debit_account = all_data['gateway_currency_lines'].get(currency_name)
                credit_account = config.get('account_id')

                if debit_account:
                    debit_accumulator[debit_account] += total
                if credit_account:
                    credit_accumulator[credit_account] += total

            donation_vals['donation_item_ids'] = donation_items
            donations_vals.append(donation_vals)

        created_donations = self.env['api.donation'].create(donations_vals)

        return {
            'created_donations': created_donations.ids,
            'debit_accumulator': debit_accumulator,
            'credit_accumulator': credit_accumulator,
            'picking_id': False,
        }

    # =========================================================
    # JOURNAL ENTRY (CHANGED ONLY HERE)
    # =========================================================

    def _create_grouped_journal_move(self, journal, debit_accumulator, credit_accumulator, company_currency, logs):

        lines = []

        for account_id, amount in debit_accumulator.items():
            if not amount:
                continue

            lines.append((0, 0, {
                'account_id': account_id,
                'amount_currency': abs(amount),
                'currency_id': company_currency.id,
                'name': 'Donation Import Debit',
            }))

        for account_id, amount in credit_accumulator.items():
            if not amount:
                continue

            lines.append((0, 0, {
                'account_id': account_id,
                'amount_currency': -abs(amount),
                'currency_id': company_currency.id,
                'name': 'Donation Import Credit',
            }))

        if not lines:
            return False

        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': fields.Date.today(),
            'ref': f'Donation Import {fields.Date.today()}',
            'line_ids': lines,
        })

        try:
            move.action_post()
        except Exception as e:
            _logger.exception("Journal Posting Failed")
            raise ValidationError(_("Journal posting failed: %s") % str(e))

        return move

    # =========================================================
    # HELPERS
    # =========================================================

    def _date_to_iso_z(self, date_val, t):
        dt = datetime.combine(date_val, t).replace(tzinfo=timezone.utc)
        return dt.isoformat(timespec='milliseconds').replace('+00:00', 'Z')