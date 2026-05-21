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
    _description = 'API Donation Wizard (Production Fixed)'

    start_date = fields.Date()
    end_date = fields.Date()

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
    # ENTRY POINT
    # =========================================================
    def action_fetch_donation(self):
        self.ensure_one()

        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError(_("Invalid date range"))

        company = self.env.company
        if not (company.url and company.client_id and company.client_secret):
            raise ValidationError(_("Missing API config"))

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
        origin_host = urlparse(base_url).hostname or ''

        auth_url = f"{company.url.rstrip('/')}/api/odoo/auth"
        donate_url = f"{company.url.rstrip('/')}/api/odoo/donationInfo"

        history = self.env['fetch.history'].create({
            'start_date': self.start_date,
            'end_date': self.end_date,
        })

        donations_info = self._fetch_donations_from_api(
            auth_url, donate_url, company, base_url, origin_host, history
        )

        if not donations_info:
            return True

        journal = self.env['account.journal'].search([('name', 'ilike', 'Bank')], limit=1)
        gateway_config = self.env['gateway.config'].search([('name', '=', 'Web API')], limit=1)

        all_data = self._prefetch_all_data(donations_info, gateway_config, company.currency_id, history)

        result = self._process_donations_bulk(
            donations_info,
            journal,
            gateway_config,
            company.currency_id,
            all_data,
            history
        )

        if result.get('accumulators') and journal:
            move = self._create_grouped_journal_move(
                journal,
                result['accumulators']['debit'],
                result['accumulators']['credit'],
                company.currency_id,
                history
            )

            history.journal_entry_id = move.id

        return True

    # =========================================================
    # API
    # =========================================================
    def _fetch_donations_from_api(self, auth_url, donate_url, company, base_url, origin_host, history):
        session = requests.Session()
        session.headers.update({'Content-Type': 'application/json'})

        token = session.post(auth_url, json={
            "ClientID": company.client_id,
            "ClientSecret": company.client_secret
        }).json().get('token')

        session.headers.update({'authorization': f'bearer {token}'})

        payload = {'status': 'success'}
        if self.start_date:
            payload['startDate'] = str(self.start_date)
        if self.end_date:
            payload['endDate'] = str(self.end_date)

        resp = session.post(donate_url, json=payload, timeout=60)
        return resp.json().get('donationsInfo', [])

    # =========================================================
    # PREFETCH
    # =========================================================
    def _prefetch_all_data(self, donations_info, gateway_config, company_currency, history):

        currencies = set()
        import_ids = set()

        for d in donations_info:
            currencies.add(d.get('currency'))
            import_ids.add(d.get('_id'))

        currency_records = self.env['res.currency'].search([
            ('name', 'in', list(currencies))
        ])

        currency_map = {c.name.lower(): c for c in currency_records}

        existing = self.env['api.donation'].search_read(
            [('import_id', 'in', list(import_ids))],
            ['import_id']
        )

        return {
            'currency_by_name': currency_map,
            'existing_import_ids': {x['import_id'] for x in existing},
            'gateway_currency_lines': {
                (l.currency_id.name.lower()): l.account_id.id
                for l in gateway_config.gateway_config_currency_ids
            },
            'gateway_product_lines': {
                (l.name or '').lower(): {
                    'account_id': l.product_id.property_account_income_id.id,
                    'product_id': l.product_id.id
                }
                for l in gateway_config.gateway_config_line_ids
            }
        }

    # =========================================================
    # PROCESS
    # =========================================================
    def _process_donations_bulk(self, donations_info, journal, gateway_config, company_currency, all_data, history):

        debit_acc = defaultdict(lambda: {'base': 0.0, 'amount_currency': 0.0})
        credit_acc = defaultdict(lambda: {'base': 0.0, 'amount_currency': 0.0})

        new_ids = []

        for info in donations_info:

            if info.get('_id') in all_data['existing_import_ids']:
                continue

            donation_vals = self._prepare_donation_vals_fast(
                info, all_data, company_currency
            )

            new_ids.append(donation_vals)

            self._accumulate(donation_vals, all_data, company_currency, debit_acc, credit_acc)

        donations = self.env['api.donation'].create(new_ids)

        return {
            'new_donations': donations.ids,
            'accumulators': {
                'debit': debit_acc,
                'credit': credit_acc
            }
        }

    # =========================================================
    # FIXED ACCUMULATION (IMPORTANT)
    # =========================================================
    def _accumulate(self, donation_vals, all_data, company_currency, debit_acc, credit_acc):

        currency = donation_vals['currency'].lower()
        currency_rec = all_data['currency_by_name'].get(currency)

        if not currency_rec:
            return

        debit_account = all_data['gateway_currency_lines'].get(currency)
        if not debit_account:
            return

        is_foreign = currency_rec.id != company_currency.id
        rate = donation_vals.get('conversion_rate', 1.0)

        for it in donation_vals.get('donation_item_ids', []):

            item = it[2]
            amount = float(item.get('total', 0))

            company_amount = amount / rate

            debit_key = (debit_account, currency_rec.id)
            credit_key = (item.get('account_id', debit_account), currency_rec.id)

            # DEBIT
            debit_acc[debit_key]['base'] += company_amount
            debit_acc[debit_key]['amount_currency'] += amount if is_foreign else 0

            # CREDIT (FIXED SIGN HANDLING)
            credit_acc[credit_key]['base'] += company_amount
            credit_acc[credit_key]['amount_currency'] += amount if is_foreign else 0

    # =========================================================
    # JOURNAL ENTRY (FIXED MULTI CURRENCY)
    # =========================================================
    def _create_grouped_journal_move(self, journal, debit_acc, credit_acc, company_currency, history):

        lines = []

        for (account_id, currency_id), vals in debit_acc.items():

            debit = company_currency.round(vals['base'])
            if not debit:
                continue

            line = {
                'account_id': account_id,
                'debit': debit,
                'credit': 0.0,
                'name': 'Donation Debit'
            }

            if currency_id != company_currency.id:
                line.update({
                    'currency_id': currency_id,
                    'amount_currency': vals['amount_currency']
                })

            lines.append((0, 0, line))

        for (account_id, currency_id), vals in credit_acc.items():

            credit = company_currency.round(vals['base'])
            if not credit:
                continue

            line = {
                'account_id': account_id,
                'debit': 0.0,
                'credit': credit,
                'name': 'Donation Credit'
            }

            if currency_id != company_currency.id:
                line.update({
                    'currency_id': currency_id,
                    'amount_currency': -abs(vals['amount_currency'])
                })

            lines.append((0, 0, line))

        move = self.env['account.move'].sudo().create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'line_ids': lines,
            'ref': 'Donation Import'
        })

        return move

    # =========================================================
    # PREPARE
    # =========================================================
    def _prepare_donation_vals_fast(self, info, all_data, company_currency):

        currency = (info.get('currency') or '').lower()

        return {
            'import_id': info.get('_id'),
            'currency': currency,
            'conversion_rate': 1.0,
            'donation_item_ids': [(0, 0, it) for it in (info.get('items') or [])],
        }