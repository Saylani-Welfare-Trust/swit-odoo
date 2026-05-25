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
    # LOGGING
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
    # MAIN ACTION
    # =========================================================

    def action_fetch_donation(self):

        self.ensure_one()
        logs = []

        if self.start_date and self.end_date and self.start_date > self.end_date:
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

            journal = self.env['account.journal'].search([
                ('type', '=', 'bank')
            ], limit=1)

            if not journal:
                raise ValidationError(_("No bank journal found."))

            gateway_config = self.env['gateway.config'].search([
                ('name', '=', 'Web API')
            ], limit=1)

            if not gateway_config:
                raise ValidationError(_("Gateway config not found."))

            all_data = self._prefetch_all_data(donations, gateway_config, company, logs)

            result = self._process_donations_bulk(
                donations,
                gateway_config,
                all_data,
                history,
                logs
            )

            move = self._create_grouped_journal_move(
                journal,
                result['lines'],
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
    # API FETCH
    # =========================================================

    def _fetch_donations_from_api(self, company, payload, logs):

        session = requests.Session()

        auth_url = f"{company.url.rstrip('/')}/api/odoo/auth"
        donate_url = f"{company.url.rstrip('/')}/api/odoo/donationInfo"

        auth_response = session.post(auth_url, json={
            "ClientID": company.client_id,
            "ClientSecret": company.client_secret
        })

        token = auth_response.json().get('token')
        if not token:
            raise ValidationError(_("Authentication token missing"))

        session.headers.update({'authorization': f'bearer {token}'})

        response = session.post(donate_url, json=payload)
        data = response.json()

        return data.get('donationsInfo', [])

    # =========================================================
    # PREFETCH
    # =========================================================

    def _prefetch_all_data(self, donations, gateway_config, company, logs):

        import_ids = {d.get('_id') for d in donations}
        mobiles = {d.get('donor_details', {}).get('phone', '')[-10:] for d in donations}

        existing_imports = self.env['api.donation'].search_read(
            [('import_id', 'in', list(import_ids))],
            ['import_id']
        )

        existing_import_ids = {x['import_id'] for x in existing_imports}

        partners = self.env['res.partner'].search_read(
            [('mobile', 'in', list(mobiles))],
            ['mobile']
        )

        partner_map = {p['mobile']: p['id'] for p in partners}

        gateway_currency_lines = {}
        for line in gateway_config.gateway_config_currency_ids:
            if line.currency_id and line.account_id:
                gateway_currency_lines[line.currency_id.name.lower()] = line.account_id.id

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
            'existing_import_ids': existing_import_ids,
            'partner_map': partner_map,
            'gateway_currency_lines': gateway_currency_lines,
            'gateway_product_lines': gateway_product_lines,
        }

    # =========================================================
    # PROCESS (FIXED MULTI-CURRENCY CORE)
    # =========================================================

    def _process_donations_bulk(self, donations, gateway_config, all_data, history, logs):

        donation_vals = []
        lines = []
        stock_accumulator = defaultdict(float)

        partner_cache = all_data['partner_map']

        for donation in donations:

            if donation.get('_id') in all_data['existing_import_ids']:
                continue

            if donation.get('status') != 'success':
                continue

            donor = donation.get('donor_details') or {}
            mobile = donor.get('phone', '')[-10:]
            currency = (donation.get('currency') or '').lower()

            partner_id = partner_cache.get(mobile)

            total_amount = float(donation.get('total_amount', 0)) - float(donation.get('bank_charges', 0))

            donation_vals.append({
                'import_id': donation.get('_id'),
                'name': donor.get('name'),
                'phone': donor.get('phone'),
                'email': donor.get('email'),
                'currency': currency,
                'total_amount': total_amount,
                'fetch_history_id': history.id,
                'donor_id': partner_id,
            })

            debit_account = all_data['gateway_currency_lines'].get(currency)

            for item in donation.get('items', []):

                total = float(item.get('total') or 0)

                product_key = (
                    f"{item.get('donationType','')}"
                    f"{item.get('item', {}).get('en', {}).get('name','')}"
                    f"{item.get('type', {}).get('en', {}).get('name','')}"
                ).strip().lower()

                config = all_data['gateway_product_lines'].get(product_key)

                if not config:
                    continue

                account_id = config['account_id']

                # STOCK
                product = self.env['product.product'].browse(config['product_id'])
                if product and product.detailed_type == 'product':
                    stock_accumulator[product.id] += float(item.get('qty') or 1)

                # ACCOUNTING (MULTI-CURRENCY SAFE)
                if debit_account:
                    lines.append((debit_account, currency, total, 'debit'))

                if account_id:
                    lines.append((account_id, currency, total, 'credit'))

        created = self.env['api.donation'].create(donation_vals)

        # STOCK
        picking_id = False
        if stock_accumulator:
            picking = self.env['stock.picking'].create({
                'picking_type_id': self.picking_type_id.id,
                'location_id': self.source_location_id.id,
                'location_dest_id': self.destination_location_id.id,
            })

            move_vals = []
            for pid, qty in stock_accumulator.items():
                product = self.env['product.product'].browse(pid)
                move_vals.append({
                    'name': product.display_name,
                    'product_id': pid,
                    'product_uom_qty': qty,
                    'picking_id': picking.id,
                    'location_id': self.source_location_id.id,
                    'location_dest_id': self.destination_location_id.id,
                    'product_uom': product.uom_id.id,
                })

            self.env['stock.move'].create(move_vals)
            picking.action_confirm()
            picking.action_assign()
            picking.button_validate()

            picking_id = picking.id

        return {
            'lines': lines,
            'picking_id': picking_id,
        }

    # =========================================================
    # JOURNAL (FINAL FIX)
    # =========================================================

    def _create_grouped_journal_move(self, journal, lines_data, logs):

        move_lines = []

        for account_id, currency, amount, typ in lines_data:

            if typ == 'debit':
                move_lines.append((0, 0, {
                    'account_id': account_id,
                    'debit': amount,
                    'credit': 0.0,
                }))
            else:
                move_lines.append((0, 0, {
                    'account_id': account_id,
                    'debit': 0.0,
                    'credit': amount,
                }))

        move = self.env['account.move'].create({
            'journal_id': journal.id,
            'move_type': 'entry',
            'line_ids': move_lines,
        })

        move.action_post()
        return move

    # =========================================================
    # DATE HELPERS
    # =========================================================

    def _date_to_iso_z(self, date_val, t):
        dt = datetime.combine(date_val, t).replace(tzinfo=timezone.utc)
        return dt.isoformat(timespec='milliseconds').replace('+00:00', 'Z')