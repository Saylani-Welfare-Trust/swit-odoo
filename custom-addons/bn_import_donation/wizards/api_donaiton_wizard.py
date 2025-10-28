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

        # validate dates
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError("Start Date must be earlier than or equal to End Date.")

        company = self.env.company
        if not (company.url and company.client_id and company.client_secret):
            raise ValidationError("Missing URL, Client ID, or Client Secret in Donation Authorization settings.")

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
        parsed = urlparse(base_url)
        origin_host = parsed.hostname or ''

        auth_url = f"{company.url.rstrip('/')}/api/odoo/auth"
        donate_url = f"{company.url.rstrip('/')}/api/odoo/donationInfo"

        session = requests.Session()
        session.headers.update({
            'Origin': base_url,
            'x-forwarded-for': origin_host,
            'Content-Type': 'application/json',
        })

        # authenticate
        token = None
        try:
            token = self._authenticate(session, auth_url, company.client_id, company.client_secret)
        except ValidationError:
            raise
        except Exception as e:
            _logger.exception('Authentication failed')
            raise ValidationError(_('Authentication failed: %s') % str(e))

        session.headers.update({'authorization': f'bearer {token}'})

        # build payload
        payload = {'status': 'success'}
        if self.start_date:
            payload['startDate'] = self._date_to_iso_z(self.start_date)
        if self.end_date:
            payload['endDate'] = self._date_to_iso_z(self.end_date)

        # fetch donations
        try:
            donations_info = self._fetch_donations(session, donate_url, payload)
        except ValidationError:
            raise
        except Exception as e:
            _logger.exception('Failed to fetch donations')
            raise ValidationError(_('Failed to fetch donations: %s') % str(e))

        if not donations_info:
            return True

        # prepare caches & config
        journal = self.env['account.journal'].search([('name', 'ilike', 'Bank')], limit=1)
        gateway_config = self.env['gateway.config'].search([('name', '=', 'Web API')], limit=1)
        company_currency = self.env.company.currency_id

        # simple caches
        currency_cache = {}
        conversion_cache = {}
        product_config_cache = {}

        new_donations = []
        debit_accumulator = {}
        credit_accumulator = {}

        # process donations within a DB savepoint; create journal in atomic block
        with self.env.cr.savepoint():
            for info in donations_info:
                import_id = info.get('_id') or ''
                if not import_id:
                    _logger.warning('Skipping donation without import id: %s', info)
                    continue

                # skip existing
                if self.env['api.donation'].search([('import_id', '=', import_id)], limit=1):
                    continue

                donation_vals = self._prepare_donation_vals(info, conversion_cache, currency_cache)

                if not donation_vals:
                    continue

                donation = self.env['api.donation'].create(donation_vals)
                new_donations.append(donation)

                # accumulate journal lines only if configuration exists
                if gateway_config and journal:
                    try:
                        self._accumulate_from_donation(donation, gateway_config, company_currency,
                                                        product_config_cache, debit_accumulator, credit_accumulator,
                                                        currency_cache)
                    except Exception:
                        _logger.exception('Failed to accumulate donation %s', donation.id)

            # create grouped journal move if we have accumulations
            if gateway_config and journal and (debit_accumulator or credit_accumulator):
                try:
                    move = self._create_grouped_journal_move(journal, debit_accumulator, credit_accumulator,
                                                             company_currency)
                    
                    fetch_history = self.env['fetch.history'].create({
                        'start_date': self.start_date,
                        'end_date': self.end_date,
                        'journal_entry_id': move.id
                    })

                    # link move to created donations
                    for d in new_donations:
                        d.fetch_history_id = fetch_history.id
                except ValidationError:
                    raise
                except Exception as e:
                    _logger.exception('Journal creation failed')
                    raise ValidationError(_('Journal Entry creation failed: %s') % str(e))

    # ---------------------- Helpers: HTTP & fetch ----------------------
    def _authenticate(self, session, url, client_id, client_secret):
        try:
            resp = session.post(url, json={"ClientID": client_id, "ClientSecret": client_secret}, timeout=30)
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

    def _get_conversion_rate(self, currency_name, currency_cache, conversion_cache):
        # returns conversion rate to company currency (float)
        if not currency_name:
            return 1.0
        if currency_name in conversion_cache:
            return conversion_cache[currency_name]

        cur = currency_cache.get(currency_name) or self.env['res.currency'].search([('name', '=', currency_name)], limit=1)
        currency_cache[currency_name] = cur
        conv = 1.0
        try:
            if cur and cur.rate_ids:
                latest_rate = cur.rate_ids.sorted(lambda r: r.name, reverse=True)[0]
                conv = float(getattr(latest_rate, 'inverse_company_rate', 1.0) or 1.0)
        except Exception:
            conv = 1.0
        conversion_cache[currency_name] = conv
        return conv

    # ---------------------- Helpers: prepare donation values ----------------------
    def _prepare_donation_vals(self, info, conversion_cache, currency_cache):
        created_dt = self._parse_iso_to_dt(info.get('createdAt'))
        updated_dt = self._parse_iso_to_dt(info.get('updatedAt'))

        currency_name = info.get('currency', '') or ''
        conv_rate = self._get_conversion_rate(currency_name, currency_cache, conversion_cache)

        total_amount = float(info.get('total_amount', 0) or 0)
        total_local = total_amount * conv_rate if currency_name != 'PKR' else total_amount

        if info.get('status') != 'success':
            return {}

        common = {
            'import_id': info.get('_id', ''),
            'remarks': info.get('remarks', ''),
            'total_amount': total_amount,
            'total_amount_local': total_local,
            'donor': info.get('donor', ''),
            'donation_type': info.get('donation_type', ''),
            'donation_from': info.get('donation_from', ''),
            'dn_number': info.get('DN_Number', ''),
            'subscription_interval': info.get('subscriptionInterval', ''),
            'is_recurring': info.get('isRecurring', False),
            'response_code': info.get('response_code', ''),
            'response_description': info.get('response_description', ''),
            'currency': currency_name,
            'referer': info.get('referer', ''),
            'website': info.get('website', ''),
            'account_source': info.get('account_source', ''),
            'conversion_rate': conv_rate,
            'bank_charges': info.get('bank_charges', 0),
            'bank_charges_in_text': info.get('bank_charges_in_text', ''),
            'blinq_notification_number': info.get('blinq_notification_number', ''),
            'created_at': created_dt,
            'updated_at': updated_dt,
            'donation_id': info.get('donation_id', ''),
            'invoice_id': info.get('invoice_id', ''),
            'transaction_id': info.get('transaction_id', ''),
        }

        donor = info.get('donor_details') or {}

        donor_id = None

        if donor.get('name', ''):
            donor_id = self.env['res.partner'].search([('mobile', '=', donor.get('phone', '')), ('category_id.name', 'in', ['Donor'])])

            if donor_id:
                donor_id = donor_id.id
            else:
                country = self.env['res.country'].search([('name', '=', donor.get('country', ''))]).id if donor.get('country', '') else None

                donor_id = self.env['res.partner'].create({
                    'name': donor.get('name', ''),
                    'mobile': donor.get('phone', ''),
                    'email': donor.get('email', ''),
                    'country_code_id': country,
                    'category_id': [(6, 0, [
                        self.env.ref('bn_profile_management.donor_partner_category').id,
                        self.env.ref('bn_profile_management.individual_partner_category').id,
                    ])]
                })

                donor_id.action_register()

                donor_id = donor_id.id
        else:
            donor_id = self.env['res.partner'].search([('primary_registration_id', '=', '2025-9999998-9')], limit=1).id


        donor_vals = {
            'name': donor.get('name', ''),
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
            'donor_id': donor_id,
        }
        common.update(donor_vals)

        # items
        items = info.get('items') or []
        orm_items = []
        for it in items:
            types = it.get('type') if isinstance(it.get('type'), dict) else {}
            item = it.get('item') if isinstance(it.get('item'), dict) else {}
            types_name = types.get('en', {}).get('name', '') if isinstance(types, dict) else ''
            item_name = item.get('en', {}).get('name', '') if isinstance(item, dict) else ''
            item_total = float(it.get('total', 0) or 0)
            orm_items.append({
                'donation_type': it.get('donationType', ''),
                'total': item_total,
                'price': it.get('price', 0),
                'price_id': it.get('price_id', 0),
                'qty': it.get('qty', 0),
                'type': types_name,
                'item': item_name,
                'donation_no': it.get('donationNo', 0),
                'is_priced_item': it.get('isPricedItem', False),
            })

        common['donation_item_ids'] = [(0, 0, it) for it in orm_items]
        return common

    # ---------------------- Helpers: accumulate journal lines ----------------------
    def _accumulate_from_donation(self, donation, gateway_config, company_currency,
                                  product_config_cache, debit_accumulator, credit_accumulator,
                                  currency_cache):
        # find debit account for donation currency
        currency_name = donation.currency or ''
        currency_rec = currency_cache.get(currency_name) or self.env['res.currency'].search([('name', '=', currency_name)], limit=1)
        currency_cache[currency_name] = currency_rec
        if not currency_rec:
            _logger.error('Currency %s not found for donation %s', currency_name, donation.id)
            return

        debit_line = gateway_config.gateway_config_currency_ids.filtered(lambda x: x.currency_id == currency_rec)
        if not debit_line:
            _logger.error('Debit account not found for currency %s', currency_name)
            return
        debit_account_id = debit_line[0].account_id.id

        is_foreign = currency_rec != company_currency

        for it in donation.donation_item_ids:
            # product key composed similarly to previous logic
            product_name = f"{it.donation_type or ''}{it.item or ''}{it.type or ''}"
            config_line = product_config_cache.get(product_name)
            if config_line is None:
                found = gateway_config.gateway_config_line_ids.filtered(lambda x: x.name == product_name)
                config_line = found[0] if found else False
                product_config_cache[product_name] = config_line

            if not config_line:
                _logger.error('Config line not found for product %s', product_name)
                continue

            credit_account = config_line.account_id
            if not credit_account:
                _logger.error('Credit account missing for product %s', product_name)
                continue

            analytic_id = config_line.analytic_account_id.id if config_line.analytic_account_id else False

            item_total = float(it.total or 0)
            conv_rate = float(donation.conversion_rate or 1.0)
            item_total_base = item_total * conv_rate if is_foreign else item_total

            # debit accumulator (group by account & currency)
            debit_key = (debit_account_id, currency_rec.id)
            d = debit_accumulator.get(debit_key, {'debit_base': 0.0, 'amount_currency': 0.0})
            d['debit_base'] += item_total_base
            if is_foreign:
                d['amount_currency'] += item_total
            debit_accumulator[debit_key] = d

            # credit accumulator (group by account, currency, analytic)
            credit_key = (credit_account.id, currency_rec.id, analytic_id)
            c = credit_accumulator.get(credit_key, {'credit_base': 0.0, 'amount_currency': 0.0, 'analytic_account_id': analytic_id})
            c['credit_base'] += item_total_base
            if is_foreign:
                c['amount_currency'] -= item_total
            credit_accumulator[credit_key] = c

    # ---------------------- Helpers: create grouped journal move ----------------------
    def _create_grouped_journal_move(self, journal, debit_accumulator, credit_accumulator, company_currency):
        journal_lines = []
        company_currency_id = company_currency.id

        for (account_id, currency_id), vals in debit_accumulator.items():
            line_vals = {
                'account_id': account_id,
                'debit': vals.get('debit_base', 0.0),
                'credit': 0.0,
                'name': 'Donation Import - Grouped Debit',
            }
            if currency_id != company_currency_id:
                line_vals['currency_id'] = currency_id
                line_vals['amount_currency'] = vals.get('amount_currency', 0.0)
            journal_lines.append((0, 0, line_vals))

        for (account_id, currency_id, analytic_id), vals in credit_accumulator.items():
            line_vals = {
                'account_id': account_id,
                'debit': 0.0,
                'credit': vals.get('credit_base', 0.0),
                'name': 'Donation Import - Grouped Credit',
            }
            if currency_id != company_currency_id:
                line_vals['currency_id'] = currency_id
                line_vals['amount_currency'] = vals.get('amount_currency', 0.0)
            if analytic_id:
                line_vals['analytic_distribution'] = {str(analytic_id): 100}
            journal_lines.append((0, 0, line_vals))

        # rounding
        debit_total = sum(l[2].get('debit', 0.0) for l in journal_lines)
        credit_total = sum(l[2].get('credit', 0.0) for l in journal_lines)
        difference = round(debit_total - credit_total, 2)

        if abs(difference) > 0.0001:
            rounding_account = self.env['account.account'].search([('code', '=', '999999')], limit=1)
            if not rounding_account:
                raise ValidationError("Rounding account with code '999999' not found. Please create or configure one.")
            rounding_line = {
                'account_id': rounding_account.id,
                'name': 'Rounding Adjustment',
                'debit': 0.0,
                'credit': 0.0,
            }
            if difference > 0:
                rounding_line['credit'] = difference
            else:
                rounding_line['debit'] = abs(difference)
            journal_lines.append((0, 0, rounding_line))

        move_vals = {
            'move_type': 'entry',
            'ref': f"Donation Import {fields.Datetime.now()}",
            'date': fields.Date.today(),
            'journal_id': journal.id,
            'line_ids': journal_lines,
        }

        move = self.env['account.move'].create(move_vals)
        move.action_post()
        return move
