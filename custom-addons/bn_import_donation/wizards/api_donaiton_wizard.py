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

        # Use session for API calls
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

        # Caches
        currency_cache = {}
        conversion_cache = {}
        product_config_cache = {}
        partner_cache = {}

        debit_accumulator = defaultdict(lambda: {'debit_base': 0.0, 'amount_currency': 0.0})
        credit_accumulator = defaultdict(lambda: {'credit_base': 0.0, 'amount_currency': 0.0, 'analytic_account_id': False})
        
        new_donations = []
        all_donation_vals = []
        
        # Default partner for missing donors
        default_partner = self.env['res.partner'].search(
            [('primary_registration_id', '=', '2025-9999998-9')], 
            limit=1
        )
        default_partner_id = default_partner.id if default_partner else False
        
        # Get donor category IDs
        donor_category = self.env.ref('bn_profile_management.donor_partner_category', raise_if_not_found=False)
        individual_category = self.env.ref('bn_profile_management.individual_partner_category', raise_if_not_found=False)
        donor_category_ids = []
        if donor_category:
            donor_category_ids.append(donor_category.id)
        if individual_category:
            donor_category_ids.append(individual_category.id)

        # Process donations one by one (simpler but still optimized)
        for info in donations_info:
            import_id = info.get('_id')
            if not import_id:
                continue

            # Check if already imported
            if self.env['api.donation'].search_count([('import_id', '=', import_id)]):
                continue

            # Prepare donation values
            donation_vals = self._prepare_donation_vals(
                info, conversion_cache, currency_cache, 
                partner_cache, donor_category_ids, default_partner_id
            )
            if not donation_vals:
                continue
                
            all_donation_vals.append(donation_vals)

            # Accumulate journal lines
            if gateway_config and journal:
                self._accumulate_from_donation(
                    donation_vals, gateway_config, company_currency,
                    product_config_cache, debit_accumulator,
                    credit_accumulator, currency_cache
                )

        # Bulk create donations
        if all_donation_vals:
            new_donations = self.env['api.donation'].create(all_donation_vals)
            
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

                # Update fetch history
                new_donations.write({'fetch_history_id': history.id})

        return True

    # ---------------------- API Methods ----------------------
    def _authenticate(self, session, url, client_id, client_secret):
        try:
            resp = session.post(url, json={"ClientID": client_id, "ClientSecret": client_secret}, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            token = data.get('token')
            if not token:
                raise ValidationError(_('Token not found in the auth response. Please check credentials.'))
            return token
        except requests.exceptions.RequestException as e:
            _logger.exception('Auth request error')
            raise ValidationError(_('Authentication request failed: %s') % str(e))
        except ValueError:
            _logger.error('Auth endpoint returned invalid JSON')
            raise ValidationError(_('Invalid JSON received from auth endpoint.'))

    def _fetch_donations(self, session, url, payload):
        try:
            resp = session.post(url, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as e:
            _logger.exception('Donations request error')
            raise ValidationError(_('Donation request failed: %s') % str(e))
        except ValueError:
            _logger.error('Donations endpoint returned invalid JSON')
            raise ValidationError(_('Invalid JSON received from donation endpoint.'))

        if not isinstance(data, dict) or 'donationsInfo' not in data:
            _logger.error('Invalid donations payload: %s', data)
            raise ValidationError(_('Invalid Donations Info'))
        return data.get('donationsInfo') or []

    # ---------------------- Data Preparation ----------------------
    def _date_to_iso_z(self, date_val):
        if not date_val:
            return None
        dt = datetime.combine(date_val, time.min).replace(tzinfo=timezone.utc)
        return dt.isoformat(timespec='milliseconds').replace('+00:00', 'Z')

    def _parse_iso_to_dt(self, iso_str):
        if not iso_str:
            return None
        try:
            return datetime.fromisoformat(iso_str.replace('Z', '+00:00')).replace(tzinfo=None)
        except Exception:
            try:
                clean = iso_str.split('.')[0].replace('T', ' ')
                return datetime.strptime(clean, '%Y-%m-%d %H:%M:%S')
            except Exception:
                _logger.warning('Failed to parse datetime: %s', iso_str)
                return None

    def _get_conversion_rate(self, currency_name, currency_cache, conversion_cache):
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
                conv = float(getattr(latest_rate, 'company_rate', 1.0) or 1.0)
        except Exception:
            conv = 1.0
        conversion_cache[currency_name] = conv
        return conv

    def _prepare_donation_vals(self, info, conversion_cache, currency_cache, 
                              partner_cache, donor_category_ids, default_partner_id):
        created_dt = self._parse_iso_to_dt(info.get('createdAt'))
        updated_dt = self._parse_iso_to_dt(info.get('updatedAt'))

        currency_name = info.get('currency', '') or ''
        conv_rate = self._get_conversion_rate(currency_name, currency_cache, conversion_cache)

        total_amount = float(info.get('total_amount', 0) or 0)
        total_local = total_amount * conv_rate

        if info.get('status') != 'success':
            return None

        # Handle donor
        donor = info.get('donor_details') or {}
        donor_id = default_partner_id
        
        if donor.get('name', ''):
            mobile = donor.get('phone', '')[-10:] if donor.get('phone') else ''
            country_code = donor.get('country', '')
            
            # Get country ID
            country_id = None
            if country_code:
                country = self.env['res.country'].search([('code', '=', country_code)], limit=1)
                if country:
                    country_id = country.id
            
            # Try to find existing partner
            if mobile and country_id:
                cache_key = (mobile, country_id)
                if cache_key in partner_cache:
                    donor_id = partner_cache[cache_key]
                else:
                    existing_partner = self.env['res.partner'].search([
                        ('mobile', '=', mobile),
                        ('country_code_id', '=', country_id),
                        ('category_id', 'in', donor_category_ids)
                    ], limit=1)
                    
                    if existing_partner:
                        donor_id = existing_partner.id
                        partner_cache[cache_key] = donor_id
                    else:
                        # Create new partner
                        new_partner = self.env['res.partner'].create({
                            'name': donor.get('name', ''),
                            'mobile': mobile,
                            'email': donor.get('email', ''),
                            'country_code_id': country_id,
                            'category_id': [(6, 0, donor_category_ids)]
                        })
                        new_partner.action_register()
                        donor_id = new_partner.id
                        partner_cache[cache_key] = donor_id

        # Prepare items
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

        return {
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
            'donation_item_ids': [(0, 0, it) for it in orm_items],
        }

    # ---------------------- Journal Accumulation ----------------------
    def _accumulate_from_donation(self, donation_vals, gateway_config, company_currency,
                                  product_config_cache, debit_accumulator, credit_accumulator,
                                  currency_cache):
        currency_name = donation_vals.get('currency', '')
        currency_rec = currency_cache.get(currency_name) or self.env['res.currency'].search([('name', '=', currency_name)], limit=1)
        currency_cache[currency_name] = currency_rec
        if not currency_rec:
            _logger.error('Currency %s not found for donation', currency_name)
            return

        debit_line = gateway_config.gateway_config_currency_ids.filtered(lambda x: x.currency_id == currency_rec)
        if not debit_line:
            _logger.error('Debit account not found for currency %s', currency_name)
            return
        debit_account_id = debit_line[0].account_id.id

        is_foreign = currency_rec != company_currency

        for it in donation_vals['donation_item_ids']:
            item = it[2]  # Get the values dict
            product_name = f"{item.get('donation_type', '')}{item.get('item', '')}{item.get('type', '')}"
            
            if product_name not in product_config_cache:
                found = gateway_config.gateway_config_line_ids.filtered(lambda x: x.name == product_name)
                product_config_cache[product_name] = found[0] if found else False
            
            config_line = product_config_cache[product_name]
            if not config_line:
                _logger.error('Config line not found for product %s', product_name)
                continue

            credit_account = config_line.account_id
            if not credit_account:
                _logger.error('Credit account missing for product %s', product_name)
                continue

            analytic_id = config_line.analytic_account_id.id if config_line.analytic_account_id else False

            item_total = float(item.get('total', 0))
            conv_rate = float(donation_vals.get('conversion_rate', 1.0))
            
            # Apply rounding
            if is_foreign:
                item_total = currency_rec.round(item_total)
            
            item_total_base = item_total * conv_rate
            item_total_base = company_currency.round(item_total_base)

            # Debit accumulator
            debit_key = (debit_account_id, currency_rec.id)
            d = debit_accumulator[debit_key]
            d['debit_base'] += item_total_base
            if is_foreign:
                d['amount_currency'] += item_total

            # Credit accumulator
            credit_key = (credit_account.id, currency_rec.id, analytic_id)
            c = credit_accumulator[credit_key]
            c['credit_base'] += item_total_base
            if is_foreign:
                c['amount_currency'] -= item_total
            c['analytic_account_id'] = analytic_id

    # ---------------------- Journal Creation ----------------------
    def _create_grouped_journal_move(self, journal, debit_accumulator, credit_accumulator, company_currency):
        lines = []
        currency = company_currency
        
        # Calculate totals with rounding
        total_debit = currency.round(sum(v['debit_base'] for v in debit_accumulator.values()))
        total_credit = currency.round(sum(v['credit_base'] for v in credit_accumulator.values()))
        
        # Add debit lines
        for (account_id, currency_id), vals in debit_accumulator.items():
            debit_amount = currency.round(vals['debit_base'])
            if debit_amount > 0:
                lines.append((0, 0, {
                    'account_id': account_id,
                    'debit': debit_amount,
                    'credit': 0.0,
                    'currency_id': currency_id if currency_id != currency.id else currency.id,
                    'amount_currency': currency.round(vals['amount_currency']) if currency_id != currency.id else 0.0,
                    'name': 'Donation Import',
                }))
        
        # Add credit lines
        for (account_id, currency_id, analytic_id), vals in credit_accumulator.items():
            credit_amount = currency.round(vals['credit_base'])
            if credit_amount > 0:
                line_vals = {
                    'account_id': account_id,
                    'debit': 0.0,
                    'credit': credit_amount,
                    'currency_id': currency_id if currency_id != currency.id else currency.id,
                    'amount_currency': currency.round(vals['amount_currency']) if currency_id != currency.id else 0.0,
                    'name': 'Donation Import',
                }
                if analytic_id:
                    line_vals['analytic_distribution'] = {str(analytic_id): 100}
                lines.append((0, 0, line_vals))
        
        # Handle rounding difference
        difference = currency.round(total_debit - total_credit)
        
        if not currency.is_zero(difference):
            # Get rounding account
            diff_account = self._get_rounding_difference_account(journal)
            
            if difference > 0:
                # Debits > Credits, add credit line
                lines.append((0, 0, {
                    'account_id': diff_account.id,
                    'debit': 0.0,
                    'credit': abs(difference),
                    'currency_id': currency.id,
                    'amount_currency': 0.0,
                    'name': 'Rounding Adjustment',
                }))
            else:
                # Credits > Debits, add debit line
                lines.append((0, 0, {
                    'account_id': diff_account.id,
                    'debit': abs(difference),
                    'credit': 0.0,
                    'currency_id': currency.id,
                    'amount_currency': 0.0,
                    'name': 'Rounding Adjustment',
                }))
        
        # Create move
        move_vals = {
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': fields.Date.today(),
            'ref': f"Donation Import {fields.Date.today()}",
            'line_ids': lines,
            'currency_id': currency.id,
        }
        
        move = self.env['account.move'].sudo().create(move_vals)
        move.action_post()
        return move

    def _get_rounding_difference_account(self, journal):
        """Get rounding difference account with fallbacks"""
        # Try journal's default account
        if journal.default_account_id:
            return journal.default_account_id
        
        company = self.env.company
        
        # Try company's difference account
        if company.difference_account_prefix:
            diff_account = self.env['account.account'].search([
                ('code', 'like', f"{company.difference_account_prefix}%"),
                ('company_id', '=', company.id)
            ], limit=1)
            if diff_account:
                return diff_account
        
        # Try expense rounding account
        diff_account = self.env['account.account'].search([
            ('account_type', 'in', ['expense', 'income']),
            ('name', 'ilike', 'rounding'),
            ('company_id', '=', company.id)
        ], limit=1)
        
        if not diff_account:
            # Last resort: get any expense account
            diff_account = self.env['account.account'].search([
                ('account_type', '=', 'expense'),
                ('company_id', '=', company.id)
            ], limit=1)
            
            if not diff_account:
                raise ValidationError(_(
                    "No suitable rounding difference account found. "
                    "Please configure a default account on journal '%s'." % journal.name
                ))
        
        return diff_account