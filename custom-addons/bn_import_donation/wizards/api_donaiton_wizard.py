from odoo import models, fields, _
from odoo.exceptions import ValidationError
from datetime import datetime, time, timezone
from urllib.parse import urlparse
import requests
import logging

_logger = logging.getLogger(__name__)


class APIDonationWizard(models.TransientModel):
    _name = 'api.donation.wizard'
    _description = 'API Donation Wizard (refactored)'


    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')


    # ---------------------- Public entry point ----------------------
    def action_fetch_donation(self):
        self.ensure_one()

        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError(_("Start Date must be earlier than or equal to End Date."))

        company = self.env.company
        if not (company.url and company.client_id and company.client_secret):
            raise ValidationError(_("Missing URL, Client ID, or Client Secret."))

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
        origin_host = urlparse(base_url).hostname or ''

        auth_url = f"{company.url.rstrip('/')}/api/odoo/auth"
        donate_url = f"{company.url.rstrip('/')}/api/odoo/donationInfo"

        session = requests.Session()
        session.headers.update({
            'Origin': base_url,
            'x-forwarded-for': origin_host,
            'Content-Type': 'application/json',
        })

        token = self._authenticate(session, auth_url, company.client_id, company.client_secret)
        session.headers.update({'authorization': f'bearer {token}'})

        payload = {'status': 'success'}
        if self.start_date:
            payload['startDate'] = self._date_to_iso_z(self.start_date)
        if self.end_date:
            payload['endDate'] = self._date_to_iso_z(self.end_date)

        donations_info = self._fetch_donations(session, donate_url, payload)
        if not donations_info:
            return True

        journal = self.env['account.journal'].search([('name', 'ilike', 'Bank')], limit=1)
        gateway_config = self.env['gateway.config'].search([('name', '=', 'Web API')], limit=1)
        company_currency = company.currency_id

        currency_cache = {}
        conversion_cache = {}
        product_config_cache = {}

        debit_accumulator = {}
        credit_accumulator = {}
        new_donations = []

        with self.env.cr.savepoint():
            for info in donations_info:
                import_id = info.get('_id')
                if not import_id:
                    continue

                if self.env['api.donation'].search_count([('import_id', '=', import_id)]):
                    continue

                vals = self._prepare_donation_vals(info, conversion_cache, currency_cache)
                if not vals:
                    continue

                donation = self.env['api.donation'].create(vals)
                new_donations.append(donation)

                if gateway_config and journal:
                    self._accumulate_from_donation(
                        donation, gateway_config, company_currency,
                        product_config_cache, debit_accumulator,
                        credit_accumulator, currency_cache
                    )

            if gateway_config and journal and (debit_accumulator or credit_accumulator):
                move = self._create_grouped_journal_move(
                    journal, debit_accumulator,
                    credit_accumulator, company_currency
                )

                history = self.env['fetch.history'].create({
                    'start_date': self.start_date,
                    'end_date': self.end_date,
                    'journal_entry_id': move.id,
                })

                for d in new_donations:
                    d.fetch_history_id = history.id

    # ---------------------- Helpers: HTTP & fetch ----------------------
    def _authenticate(self, session, url, client_id, client_secret):
        try:
            resp = session.post(url, json={"ClientID": client_id, "ClientSecret": client_secret}, timeout=60)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as e:
            _logger.exception('Auth request error')
            raise ValidationError(_('Authentication request failed: %s') % str(e))
        except ValueError:
            _logger.error('Auth endpoint returned invalid JSON: %s', getattr(resp, 'text', ''))
            raise ValidationError(_('Invalid JSON received from auth endpoint.'))

        token = data.get('token')
        if not token:
            raise ValidationError(_('Token not found in the auth response. Please check credentials.'))
        return token

    def _fetch_donations(self, session, url, payload):
        try:
            resp = session.post(url, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as e:
            _logger.exception('Donations request error')
            raise ValidationError(_('Donation request failed: %s') % str(e))
        except ValueError:
            _logger.error('Donations endpoint returned invalid JSON: %s', getattr(resp, 'text', ''))
            raise ValidationError(_('Invalid JSON received from donation endpoint.'))

        if not isinstance(data, dict) or 'donationsInfo' not in data:
            _logger.error('Invalid donations payload: %s', data)
            raise ValidationError(_('Invalid Donations Info'))
        return data.get('donationsInfo') or []

    # ---------------------- Helpers: data parsing & conversion ----------------------
    def _date_to_iso_z(self, date_val):
        # date_val is a datetime.date; return ISO z string at midnight UTC with ms precision
        if not date_val:
            return None
        dt = datetime.combine(date_val, time.min).replace(tzinfo=timezone.utc)
        return dt.isoformat(timespec='milliseconds').replace('+00:00', 'Z')

    def _parse_iso_to_dt(self, iso_str):
        if not iso_str:
            return None
        try:
            # try strict ISO first
            return datetime.fromisoformat(iso_str.replace('Z', '+00:00')).replace(tzinfo=None)
        except Exception:
            try:
                # fallback to looser parsing
                clean = iso_str.split('.')[0].replace('T', ' ')
                return datetime.strptime(clean, '%Y-%m-%d %H:%M:%S')
            except Exception:
                _logger.warning('Failed to parse datetime: %s', iso_str)
                return None

    def _convert_to_company_currency(self, amount, currency):
        company = self.env.company
        if not currency or currency == company.currency_id:
            return amount

        return currency._convert(
            amount,
            company.currency_id,
            company,
            fields.Date.today()
        )

    # ---------------------- Helpers: prepare donation values ----------------------
    def _prepare_donation_vals(self, info, conversion_cache, currency_cache):
        created_dt = self._parse_iso_to_dt(info.get('createdAt'))
        updated_dt = self._parse_iso_to_dt(info.get('updatedAt'))

        if info.get('status') != 'success':
            return {}

        currency_name = info.get('currency', '') or ''
        currency = currency_cache.get(currency_name)
        if not currency:
            currency = self.env['res.currency'].search([('name', '=', currency_name)], limit=1)
            currency_cache[currency_name] = currency

        if not currency:
            _logger.error("Currency not found: %s", currency_name)
            return {}

        total_amount = float(info.get('total_amount', 0) or 0.0)

        common = {
            'import_id': info.get('_id', ''),
            'remarks': info.get('remarks', ''),
            'total_amount': total_amount,          # ALWAYS foreign amount
            'currency_id': currency.id,             # REQUIRED
            'donor': info.get('donor', ''),
            'donation_type': info.get('donation_type', ''),
            'donation_from': info.get('donation_from', ''),
            'dn_number': info.get('DN_Number', ''),
            'subscription_interval': info.get('subscriptionInterval', ''),
            'is_recurring': info.get('isRecurring', False),
            'response_code': info.get('response_code', ''),
            'response_description': info.get('response_description', ''),
            'referer': info.get('referer', ''),
            'website': info.get('website', ''),
            'account_source': info.get('account_source', ''),
            'bank_charges': info.get('bank_charges', 0),
            'bank_charges_in_text': info.get('bank_charges_in_text', ''),
            'blinq_notification_number': info.get('blinq_notification_number', ''),
            'created_at': created_dt,
            'updated_at': updated_dt,
            'donation_id': info.get('donation_id', ''),
            'invoice_id': info.get('invoice_id', ''),
            'transaction_id': info.get('transaction_id', ''),
        }

        # ---------------- Donor handling ----------------
        donor = info.get('donor_details') or {}
        donor_id = False

        if donor.get('name'):
            mobile = (donor.get('phone') or '')[-10:]
            country = False

            if donor.get('country'):
                country = self.env['res.country'].search(
                    [('code', '=', donor.get('country'))], limit=1
                ).id

            donor_partner = self.env['res.partner'].search([
                ('mobile', '=', mobile),
                ('category_id.name', 'in', ['Donor']),
            ], limit=1)

            if donor_partner:
                donor_id = donor_partner.id
            else:
                donor_partner = self.env['res.partner'].create({
                    'name': donor.get('name'),
                    'mobile': mobile,
                    'email': donor.get('email'),
                    'country_id': country,
                    'category_id': [(6, 0, [
                        self.env.ref('bn_profile_management.donor_partner_category').id,
                        self.env.ref('bn_profile_management.individual_partner_category').id,
                    ])]
                })
                donor_partner.action_register()
                donor_id = donor_partner.id
        else:
            donor_id = self.env['res.partner'].search(
                [('primary_registration_id', '=', '2025-9999998-9')],
                limit=1
            ).id

        common.update({
            'donor_id': donor_id,
            'phone': donor.get('phone', ''),
            'email': donor.get('email', ''),
            'cnic': donor.get('cnic', ''),
            'country': donor.get('country', ''),
            'ip_address': donor.get('ipAddress', ''),
            'subscription_for_news': donor.get('subscriptionForNews', False),
            'subscription_for_whatsapp': donor.get('subscriptionForWhatsapp', False),
            'subscription_for_sms': donor.get('subscriptionForSms', False),
            'qurbani_country': donor.get('qurbaniCountry', ''),
            'qurbani_city': donor.get('qurbaniCity', ''),
            'qurbani_day': donor.get('qurbaniDay', ''),
        })

        # ---------------- Donation items ----------------
        items = info.get('items') or []
        orm_items = []

        for it in items:
            types = it.get('type') or {}
            item = it.get('item') or {}

            orm_items.append({
                'donation_type': it.get('donationType', ''),
                'total': float(it.get('total', 0) or 0.0),  # foreign currency
                'price': it.get('price', 0),
                'price_id': it.get('price_id', 0),
                'qty': it.get('qty', 0),
                'type': types.get('en', {}).get('name', ''),
                'item': item.get('en', {}).get('name', ''),
                'donation_no': it.get('donationNo', 0),
                'is_priced_item': it.get('isPricedItem', False),
            })

        common['donation_item_ids'] = [(0, 0, line) for line in orm_items]
        return common

    # ---------------------- Helpers: accumulate journal lines ----------------------
    def _accumulate_from_donation(self, donation, gateway_config, company_currency, product_config_cache, debit_accumulator, credit_accumulator, currency_cache):
        currency_name = donation.currency or ''
        currency = currency_cache.get(currency_name)
        if not currency:
            currency = self.env['res.currency'].search([('name', '=', currency_name)], limit=1)
            currency_cache[currency_name] = currency

        if not currency:
            _logger.error("Currency %s not found", currency_name)
            return

        debit_cfg = gateway_config.gateway_config_currency_ids.filtered(
            lambda x: x.currency_id == currency
        )
        if not debit_cfg:
            _logger.error("Debit account missing for %s", currency_name)
            return

        debit_account = debit_cfg[0].account_id.id

        for item in donation.donation_item_ids:
            product_key = f"{item.donation_type or ''}{item.item or ''}{item.type or ''}"

            config = product_config_cache.get(product_key)
            if config is None:
                found = gateway_config.gateway_config_line_ids.filtered(lambda x: x.name == product_key)
                config = found[:1]
                product_config_cache[product_key] = config

            if not config or not config.account_id:
                _logger.error("Missing credit config for %s", product_key)
                continue

            amount_foreign = float(item.total or 0.0)
            amount_company = self._convert_to_company_currency(amount_foreign, currency)

            # ---------------- DEBIT ----------------
            d_key = (debit_account, currency.id)
            debit_accumulator[d_key] = debit_accumulator.get(d_key, 0.0) + amount_company

            # ---------------- CREDIT ----------------
            analytic_id = config.analytic_account_id.id if config.analytic_account_id else False
            c_key = (config.account_id.id, currency.id, analytic_id)
            credit_accumulator[c_key] = credit_accumulator.get(c_key, 0.0) + amount_company

    # ---------------------- Helpers: create grouped journal move ----------------------
    def _create_grouped_journal_move(self, journal, debit_accumulator, credit_accumulator, company_currency):
        lines = []

        # ---------------- DEBIT LINES ----------------
        for (account_id, currency_id), balance in debit_accumulator.items():
            lines.append((0, 0, {
                'account_id': account_id,
                'balance': balance,
                'currency_id': currency_id if currency_id != company_currency.id else False,
                'name': 'Donation Import - Debit',
            }))

        # ---------------- CREDIT LINES ----------------
        for (account_id, currency_id, analytic_id), balance in credit_accumulator.items():
            vals = {
                'account_id': account_id,
                'balance': -balance,
                'currency_id': currency_id if currency_id != company_currency.id else False,
                'name': 'Donation Import - Credit',
            }
            if analytic_id:
                vals['analytic_distribution'] = {str(analytic_id): 100}
            lines.append((0, 0, vals))

        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': fields.Date.today(),
            'ref': f"Donation Import {fields.Datetime.now()}",
            'line_ids': lines,
        })

        move.action_post()
        return move