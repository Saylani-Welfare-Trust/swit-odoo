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
    _description = 'API Donation Wizard (refactored)'

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
        string="Source Location",
        store=True
    )

    destination_location_id = fields.Many2one(
        related='picking_type_id.default_location_dest_id',
        string="Destination Location",
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
    # MAIN ENTRY
    # =========================================================
    def action_fetch_donation(self):
        self.ensure_one()

        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError(_("Start Date must be earlier than End Date"))

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

        donations_info = self._fetch_donations_from_api(
            auth_url, donate_url, company, base_url, origin_host, history
        )

        if not donations_info:
            return True

        journal = self.env['account.journal'].search([('name', 'ilike', 'Bank')], limit=1)
        gateway_config = self.env['gateway.config'].search([('name', '=', 'Web API')], limit=1)
        company_currency = company.currency_id

        all_data = self._prefetch_all_data(donations_info, gateway_config, company_currency, history)

        result = self._process_donations_bulk(
            donations_info, journal, gateway_config, company_currency, all_data, history
        )

        if result.get('new_donations') and journal:
            move = self._create_grouped_journal_move(
                journal,
                result['accumulators']['debit'],
                result['accumulators']['credit'],
                company_currency,
                history
            )

            history.write({
                'journal_entry_id': move.id,
                'picking_id': result.get('picking_id')
            })

        return True

    # =========================================================
    # API FETCH
    # =========================================================
    def _fetch_donations_from_api(self, auth_url, donate_url, company, base_url, origin_host, history):
        with requests.Session() as session:
            token = self._authenticate(session, auth_url, company.client_id, company.client_secret)
            session.headers.update({'authorization': f'bearer {token}'})

            payload = {'status': 'success'}

            if self.start_date:
                payload['startDate'] = self._date_to_iso_z(self.start_date)
            if self.end_date:
                payload['endDate'] = self._date_to_iso_z(self.end_date)

            resp = session.post(donate_url, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()

            return data.get('donationsInfo', [])

    def _authenticate(self, session, url, client_id, client_secret):
        resp = session.post(url, json={
            "ClientID": client_id,
            "ClientSecret": client_secret
        }, timeout=30)
        resp.raise_for_status()
        return resp.json().get('token')

    # =========================================================
    # PREFETCH DATA
    # =========================================================
    def _prefetch_all_data(self, donations_info, gateway_config, company_currency, history):

        currencies = set()
        imports = set()
        countries = set()
        mobiles = set()

        for i in donations_info:
            if i.get('_id'):
                imports.add(i['_id'])
            if i.get('currency'):
                currencies.add(i['currency'])
            donor = i.get('donor_details') or {}
            if donor.get('country'):
                countries.add(donor['country'])
            if donor.get('phone'):
                mobiles.add(donor['phone'][-10:])

        currency_recs = self.env['res.currency'].search([('name', 'in', list(currencies))])
        currency_map = {c.name.lower(): c for c in currency_recs}

        conversion = {
            c.name.lower(): (c.rate_ids[:1].company_rate if c.rate_ids else 1.0)
            for c in currency_recs
        }

        country_map = {
            c.code: c.id for c in self.env['res.country'].search([('code', 'in', list(countries))])
        }

        existing = set(
            r['import_id']
            for r in self.env['api.donation'].search_read(
                [('import_id', 'in', list(imports))],
                ['import_id']
            )
        )

        partner_cache = {}
        donor_cat = self.env.ref('bn_profile_management.donor_partner_category', False)

        for p in self.env['res.partner'].search_read(
            [('mobile', 'in', list(mobiles))],
            ['id', 'mobile', 'country_code_id', 'category_id']
        ):
            if donor_cat and donor_cat.id in (p.get('category_id') or []):
                cc = p.get('country_code_id')
                cc = cc[0] if cc else False
                partner_cache[(p['mobile'], cc)] = p['id']

        return {
            'currency_by_name': currency_map,
            'conversion_rates': conversion,
            'country_by_code': country_map,
            'existing_import_ids': existing,
            'partner_cache': partner_cache,
        }

    # =========================================================
    # PROCESS BULK
    # =========================================================
    def _process_donations_bulk(self, donations_info, journal, gateway_config, company_currency, all_data, history):

        debit = defaultdict(lambda: {'debit_base': 0.0, 'amount_currency': 0.0})
        credit = defaultdict(lambda: {'credit_base': 0.0, 'amount_currency': 0.0})

        new_ids = []
        stock = defaultdict(float)

        for info in donations_info:

            if info.get('_id') in all_data['existing_import_ids']:
                continue

            vals = self._prepare_donation_vals_fast(
                info, all_data, 0, [], {}, history
            )

            if not vals:
                continue

            new_ids.append(vals.get('import_id'))

            self._accumulate_donation_lines_fast(
                vals, all_data, company_currency,
                debit, credit, history
            )

        return {
            'new_donations': new_ids,
            'accumulators': {'debit': debit, 'credit': credit},
            'picking_id': False
        }

    # =========================================================
    # ACCUMULATOR FIXED
    # =========================================================
    def _accumulate_donation_lines_fast(self, donation_vals, all_data, company_currency,
                                        debit_accumulator, credit_accumulator, history):

        currency = donation_vals.get('currency', '').lower()
        currency_rec = all_data['currency_by_name'].get(currency)

        if not currency_rec:
            return

        debit_acc = all_data['gateway_currency_lines'].get(currency)
        if not debit_acc:
            return

        is_foreign = currency_rec != company_currency

        for it in donation_vals.get('donation_item_ids', []):

            item = it[2]

            product_key = (
                f"{item.get('donation_type','')}"
                f"{item.get('item','')}"
                f"{item.get('type','')}"
            ).strip().lower()

            config = all_data['gateway_product_lines'].get(product_key)
            if not config:
                continue

            credit_acc = config['account_id']

            amount = float(item.get('total', 0) or 0)

            base = company_currency.round(amount)

            key_d = (debit_acc, currency_rec.id)
            d = debit_accumulator[key_d]
            d['debit_base'] += base
            if is_foreign:
                d['amount_currency'] += abs(amount)

            key_c = (credit_acc, currency_rec.id)
            c = credit_accumulator[key_c]
            c['credit_base'] += base
            if is_foreign:
                c['amount_currency'] -= abs(amount)

    # =========================================================
    # JOURNAL FIXED (MOST IMPORTANT)
    # =========================================================
    def _create_grouped_journal_move(self, journal, debit_accumulator, credit_accumulator, company_currency, history):

        lines = []
        total_debit = 0
        total_credit = 0

        for (acc, cur), v in debit_accumulator.items():
            amt = company_currency.round(v['debit_base'])
            if not amt:
                continue

            lines.append((0, 0, {
                'account_id': acc,
                'debit': amt,
                'credit': 0.0,
                'currency_id': cur if cur != company_currency.id else False,
                'amount_currency': v['amount_currency'] if cur != company_currency.id else 0.0,
            }))
            total_debit += amt

        for (acc, cur), v in credit_accumulator.items():
            amt = company_currency.round(v['credit_base'])
            if not amt:
                continue

            lines.append((0, 0, {
                'account_id': acc,
                'debit': 0.0,
                'credit': amt,
                'currency_id': cur if cur != company_currency.id else False,
                'amount_currency': v['amount_currency'] if cur != company_currency.id else 0.0,
            }))
            total_credit += amt

        diff = company_currency.round(total_debit - total_credit)

        if diff:
            diff_acc = self._get_rounding_difference_account(journal, history)

            lines.append((0, 0, {
                'account_id': diff_acc.id,
                'debit': abs(diff) if diff < 0 else 0.0,
                'credit': diff if diff > 0 else 0.0,
                'name': 'Rounding',
            }))

        return self.env['account.move'].sudo().create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'line_ids': lines,
            'date': fields.Date.today(),
        })

    # =========================================================
    def _get_rounding_difference_account(self, journal, history):
        return journal.default_account_id or self.env['account.account'].search([
            ('account_type', '=', 'expense')
        ], limit=1)

    # =========================================================
    def _date_to_iso_z(self, date_val):
        return datetime.combine(date_val, time.min).replace(tzinfo=timezone.utc).isoformat()