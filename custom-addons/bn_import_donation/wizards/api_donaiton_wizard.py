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

        # Fetch all required data in bulk before processing
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
        origin_host = urlparse(base_url).hostname or ''

        auth_url = f"{company.url.rstrip('/')}/api/odoo/auth"
        donate_url = f"{company.url.rstrip('/')}/api/odoo/donationInfo"

        # Get donations from API
        donations_info = self._fetch_donations_from_api(auth_url, donate_url, company, base_url, origin_host)
        if not donations_info:
            return True

        # Prepare bulk data
        journal = self.env['account.journal'].search([('name', 'ilike', 'Bank')], limit=1)
        gateway_config = self.env['gateway.config'].search([('name', '=', 'Web API')], limit=1)
        company_currency = company.currency_id
        
        # Pre-fetch all required data in bulk
        all_data = self._prefetch_all_data(donations_info, gateway_config, company_currency)
        
        # Process donations in optimized way
        result = self._process_donations_bulk(
            donations_info, journal, gateway_config, company_currency, all_data
        )
        
        if result.get('new_donations') and journal and result.get('accumulators'):
            move = self._create_grouped_journal_move(
                journal, 
                result['accumulators']['debit'],
                result['accumulators']['credit'], 
                company_currency
            )

            history = self.env['fetch.history'].create({
                'start_date': self.start_date,
                'end_date': self.end_date,
                'journal_entry_id': move.id,
            })

            # Bulk update fetch history
            if result['new_donations']:
                self.env['api.donation'].browse(result['new_donations']).write({
                    'fetch_history_id': history.id
                })

        return True

    # ---------------------- Bulk API Operations ----------------------
    def _fetch_donations_from_api(self, auth_url, donate_url, company, base_url, origin_host):
        """Fetch donations from API with optimized session handling"""
        try:
            with requests.Session() as session:
                session.headers.update({
                    'Origin': base_url,
                    'x-forwarded-for': origin_host,
                    'Content-Type': 'application/json',
                })

                # Authenticate
                token = self._authenticate(session, auth_url, company.client_id, company.client_secret)
                session.headers.update({'authorization': f'bearer {token}'})

                # Prepare payload
                payload = {'status': 'success'}
                if self.start_date:
                    payload['startDate'] = self._date_to_iso_z(self.start_date)
                if self.end_date:
                    payload['endDate'] = self._date_to_iso_z(self.end_date)

                # Fetch donations
                resp = session.post(donate_url, json=payload, timeout=60)
                resp.raise_for_status()
                data = resp.json()

                if not isinstance(data, dict) or 'donationsInfo' not in data:
                    _logger.error('Invalid donations payload: %s', data)
                    raise ValidationError(_('Invalid Donations Info'))
                    
                return data.get('donationsInfo') or []

        except requests.exceptions.RequestException as e:
            _logger.exception('API request error')
            raise ValidationError(_('API request failed: %s') % str(e))
        except ValueError as e:
            _logger.error('Invalid JSON response: %s', str(e))
            raise ValidationError(_('Invalid JSON received from API.'))

    def _authenticate(self, session, url, client_id, client_secret):
        """Authenticate with API"""
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

    # ---------------------- Bulk Data Pre-fetching ----------------------
    def _prefetch_all_data(self, donations_info, gateway_config, company_currency):
        unique_import_ids = set()
        unique_currencies = set()
        unique_country_codes = set()
        unique_mobiles = set()

        for info in donations_info:
            if info.get('_id'):
                unique_import_ids.add(info['_id'])

            if info.get('currency'):
                unique_currencies.add(info['currency'])

            donor = info.get('donor_details') or {}
            if donor.get('country'):
                unique_country_codes.add(donor['country'])

            if donor.get('phone'):
                mobile = donor['phone'][-10:]
                unique_mobiles.add(mobile)

        # -------------------------
        # Currency
        # -------------------------
        currencies = self.env['res.currency'].search([('name', 'in', list(unique_currencies))])
        currency_by_name = {c.name: c for c in currencies}

        conversion_rates = {}
        for c in currencies:
            rate = c.rate_ids.sorted('name', reverse=True)[:1]
            conversion_rates[c.name] = rate.company_rate if rate else 1.0

        # -------------------------
        # Countries
        # -------------------------
        countries = self.env['res.country'].search([('code', 'in', list(unique_country_codes))])
        country_by_code = {c.code: c.id for c in countries}

        # -------------------------
        # Existing Donations
        # -------------------------
        existing_import_ids = {
            r['import_id']
            for r in self.env['api.donation'].search_read(
                [('import_id', 'in', list(unique_import_ids))],
                ['import_id']
            )
        }

        # -------------------------
        # EXISTING DONORS (KEY FIX)
        # -------------------------
        donor_category = self.env.ref('bn_profile_management.donor_partner_category', False)

        donor_map = {}
        if unique_mobiles and donor_category:
            donors = self.env['res.partner'].search_read(
                [
                    ('state', '=', 'register'),
                    ('category_id', 'in', [donor_category.id]),
                    ('mobile', 'in', list(unique_mobiles)),
                ],
                ['id', 'mobile', 'country_code_id']
            )

            for d in donors:
                donor_map[(d['mobile'], d['country_code_id'] and d['country_code_id'][0])] = d['id']

        # -------------------------
        # Gateway Config
        # -------------------------
        gateway_currency_lines = {
            l.currency_id.name: l.account_id.id
            for l in gateway_config.gateway_config_currency_ids
        } if gateway_config else {}

        gateway_product_lines = {
            l.name: {
                'account_id': l.account_id.id,
                'analytic_id': l.analytic_account_id.id if l.analytic_account_id else False
            }
            for l in gateway_config.gateway_config_line_ids
        } if gateway_config else {}

        default_partner = self.env['res.partner'].search(
            [('primary_registration_id', '=', '2025-9999998-9')], limit=1
        )

        return {
            'currency_by_name': currency_by_name,
            'conversion_rates': conversion_rates,
            'country_by_code': country_by_code,
            'existing_import_ids': existing_import_ids,
            'donor_map': donor_map,          # ✅ IMPORTANT
            'gateway_currency_lines': gateway_currency_lines,
            'gateway_product_lines': gateway_product_lines,
            'default_partner_id': default_partner.id if default_partner else False,
        }

    # ---------------------- Bulk Processing ----------------------
    def _process_donations_bulk(self, donations_info, journal, gateway_config, company_currency, all_data):
        """Process donations in bulk with optimized operations"""
        new_donation_ids = []
        debit_accumulator = defaultdict(lambda: {'debit_base': 0.0, 'amount_currency': 0.0})
        credit_accumulator = defaultdict(lambda: {'credit_base': 0.0, 'amount_currency': 0.0, 'analytic_account_id': False})
        
        # Prepare bulk create data
        donations_to_create = []
        partner_to_create = []
        partner_mapping = {}
        
        for info_idx, info in enumerate(donations_info):
            import_id = info.get('_id')
            if not import_id or import_id in all_data['existing_import_ids']:
                continue

            # Prepare donation values efficiently
            donation_vals = self._prepare_donation_vals_fast(info, all_data, info_idx, partner_to_create, partner_mapping)
            if donation_vals:
                donations_to_create.append(donation_vals)
                
                # Accumulate journal lines if gateway config exists
                if gateway_config and journal:
                    self._accumulate_donation_lines_fast(
                        donation_vals, all_data, company_currency,
                        debit_accumulator, credit_accumulator
                    )
        
        # Bulk create partners first
        if partner_to_create:
            created_partners = self.env['res.partner'].create(partner_to_create)
            # Register partners in bulk
            created_partners.action_register()
            # Update mapping with new IDs
            # for idx, partner in enumerate(created_partners):
            #     original_idx = partner_to_create[idx].get('original_index')
            #     if original_idx is not None:
            #         partner_mapping[original_idx] = partner.id
        
        # Update partner IDs in donation values
        for donation_val in donations_to_create:
            if 'partner_key' in donation_val:
                donation_val['donor_id'] = partner_mapping.get(donation_val['partner_key'])
                del donation_val['partner_key']
        
        # Bulk create donations
        if donations_to_create:
            new_donations = self.env['api.donation'].create(donations_to_create)
            new_donation_ids = new_donations.ids
        
        return {
            'new_donations': new_donation_ids,
            'accumulators': {
                'debit': dict(debit_accumulator),
                'credit': dict(credit_accumulator)
            }
        }

    def _prepare_donation_vals_fast(self, info, all_data, info_idx, partner_to_create, partner_mapping):
        """Prepare donation values with optimized lookups"""
        if info.get('status') != 'success':
            return None
        
        # Parse dates
        created_dt = self._parse_iso_to_dt_fast(info.get('createdAt'))
        updated_dt = self._parse_iso_to_dt_fast(info.get('updatedAt'))
        
        # Get currency and conversion rate - ensure we have a valid currency
        currency_name = info.get('currency', '') or ''
        conv_rate = all_data['conversion_rates'].get(currency_name, 1.0)
        
        # Validate currency exists
        if currency_name and currency_name not in all_data['currency_by_name']:
            _logger.warning(f"Currency {currency_name} not found in system, using company currency")
            # Use company currency as fallback
            currency_name = self.env.company.currency_id.name
            conv_rate = 1.0
        
        # Calculate amounts
        total_amount = float(info.get('total_amount', 0) or 0)
        total_local = total_amount * conv_rate
        
        # Prepare donor info
        donor = info.get('donor_details') or {}
        mobile = donor.get('phone', '')[-10:] if donor.get('phone') else ''
        country_code = donor.get('country', '')
        country_id = all_data['country_by_code'].get(country_code)
        donor_id = None
        partner_key = None
        donor_id = all_data['donor_map'].get((mobile, country_id))
        
        if not donor_id and donor.get('name', ''):
            # Create new partner
            partner_vals = {
                'name': donor.get('name', ''),
                'mobile': mobile,
                'email': donor.get('email', ''),
                'country_code_id': country_id,
                'category_id': [(6, 0, [cid for cid in all_data['donor_category_ids'] if cid])],
                # 'original_index': len(partner_to_create)  # Store index for mapping
            }
            partner_to_create.append(partner_vals)
            # Temporary key for later mapping
            partner_key = len(partner_to_create) - 1
        else:
            donor_id = all_data['default_partner_id']
        
        # Prepare donation items
        items = info.get('items') or []
        orm_items = []
        for it in items:
            types_name = ''
            item_name = ''
            
            # Fast extraction of type and item names
            type_data = it.get('type', {})
            if isinstance(type_data, dict) and 'en' in type_data:
                types_name = type_data.get('en', {}).get('name', '')
            
            item_data = it.get('item', {})
            if isinstance(item_data, dict) and 'en' in item_data:
                item_name = item_data.get('en', {}).get('name', '')
            
            orm_items.append({
                'donation_type': it.get('donationType', ''),
                'total': float(it.get('total', 0) or 0),
                'price': it.get('price', 0),
                'price_id': it.get('price_id', 0),
                'qty': it.get('qty', 0),
                'type': types_name,
                'item': item_name,
                'donation_no': it.get('donationNo', 0),
                'is_priced_item': it.get('isPricedItem', False),
            })
        
        # Build donation values
        donation_vals = {
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
            'donation_item_ids': [(0, 0, it) for it in orm_items],
        }
        
        # Set donor_id - either from cache, from new partner, or default
        if donor_id:
            donation_vals['donor_id'] = donor_id
        elif partner_key is not None:
            donation_vals['partner_key'] = partner_key
        else:
            donation_vals['donor_id'] = all_data['default_partner_id']
        
        return donation_vals

    def _accumulate_donation_lines_fast(self, donation_vals, all_data, company_currency, 
                                        debit_accumulator, credit_accumulator):
        """Accumulate journal lines with optimized lookups"""
        currency_name = donation_vals.get('currency', '')
        currency_rec = all_data['currency_by_name'].get(currency_name)
        if not currency_rec:
            _logger.warning(f"Currency {currency_name} not found for donation")
            return
        
        # Get debit account from cache
        debit_account_id = all_data['gateway_currency_lines'].get(currency_name)
        if not debit_account_id:
            _logger.warning(f"Debit account not found for currency {currency_name}")
            return
        
        is_foreign = currency_rec != company_currency
        
        # Process items
        for it in donation_vals.get('donation_item_ids', []):
            item = it[2]  # (0, 0, values) format
            product_name = f"{item.get('donation_type', '')}{item.get('item', '')}{item.get('type', '')}"
            
            config = all_data['gateway_product_lines'].get(product_name)
            if not config:
                _logger.warning(f"Product config not found for {product_name}")
                continue
            
            credit_account_id = config['account_id']
            analytic_id = config['analytic_id']
            
            item_total = float(item.get('total', 0))
            conv_rate = float(donation_vals.get('conversion_rate', 1.0))
            
            # Apply rounding at the item level
            if is_foreign:
                # Round foreign amount to currency precision
                item_total = currency_rec.round(item_total)
            
            item_total_base = item_total * conv_rate
            # Round base amount to company currency precision
            item_total_base = company_currency.round(item_total_base)
            
            # Ensure we have a currency ID
            currency_id = currency_rec.id if currency_rec else company_currency.id
            
            # Accumulate debit
            debit_key = (debit_account_id, currency_id)
            d = debit_accumulator[debit_key]
            d['debit_base'] += item_total_base
            if is_foreign:
                d['amount_currency'] += item_total
            
            # Accumulate credit
            credit_key = (credit_account_id, currency_id, analytic_id)
            c = credit_accumulator[credit_key]
            c['credit_base'] += item_total_base
            if is_foreign:
                c['amount_currency'] -= item_total
            c['analytic_account_id'] = analytic_id

    # ---------------------- Optimized Helper Methods ----------------------
    def _date_to_iso_z(self, date_val):
        """Convert date to ISO Z format"""
        if not date_val:
            return None
        dt = datetime.combine(date_val, time.min).replace(tzinfo=timezone.utc)
        return dt.isoformat(timespec='milliseconds').replace('+00:00', 'Z')

    def _parse_iso_to_dt_fast(self, iso_str):
        """Fast ISO datetime parsing"""
        if not iso_str:
            return None
        try:
            # Most common format first
            if 'T' in iso_str:
                # Handle ISO format with Z or timezone
                if 'Z' in iso_str:
                    return datetime.fromisoformat(iso_str.replace('Z', '+00:00')).replace(tzinfo=None)
                elif '+' in iso_str or '-' in iso_str[10:]:  # Has timezone offset
                    return datetime.fromisoformat(iso_str).replace(tzinfo=None)
                else:
                    return datetime.fromisoformat(iso_str)
            else:
                # Try common date formats
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d']:
                    try:
                        return datetime.strptime(iso_str, fmt)
                    except ValueError:
                        continue
                # Fallback to naive parsing
                return datetime.strptime(iso_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
        except Exception:
            _logger.debug('Failed to parse datetime: %s', iso_str)
            return None

    # ---------------------- Journal Entry Creation ----------------------
    def _create_grouped_journal_move(self, journal, debit_accumulator, credit_accumulator, company_currency):
        """Create journal entry with optimized line creation"""
        lines = []
        currency = company_currency
        
        # Calculate totals with proper rounding
        total_debit = currency.round(sum(v['debit_base'] for v in debit_accumulator.values()))
        total_credit = currency.round(sum(v['credit_base'] for v in credit_accumulator.values()))
        
        _logger.info(f"Total Debit: {total_debit}, Total Credit: {total_credit}")
        
        # Add debit lines with proper rounding
        for (account_id, currency_id), vals in debit_accumulator.items():
            debit_amount = currency.round(vals['debit_base'])
            if debit_amount > 0:
                line_currency_id = currency_id or currency.id
                line_vals = {
                    'account_id': account_id,
                    'debit': debit_amount,
                    'credit': 0.0,
                    'currency_id': line_currency_id,
                    'amount_currency': currency.round(vals['amount_currency']) if line_currency_id != currency.id else 0.0,
                    'name': 'Donation Import - Debit',
                }
                lines.append((0, 0, line_vals))
        
        # Add credit lines with proper rounding
        for (account_id, currency_id, analytic_id), vals in credit_accumulator.items():
            credit_amount = currency.round(vals['credit_base'])
            if credit_amount > 0:
                line_currency_id = currency_id or currency.id
                line_vals = {
                    'account_id': account_id,
                    'debit': 0.0,
                    'credit': credit_amount,
                    'currency_id': line_currency_id,
                    'amount_currency': currency.round(vals['amount_currency']) if line_currency_id != currency.id else 0.0,
                    'name': 'Donation Import - Credit',
                }
                if analytic_id:
                    line_vals['analytic_distribution'] = {str(analytic_id): 100}
                lines.append((0, 0, line_vals))
        
        # Recalculate totals from lines to ensure accuracy
        line_debits = sum(line[2]['debit'] for line in lines)
        line_credits = sum(line[2]['credit'] for line in lines)
        
        _logger.info(f"Line Debits: {line_debits}, Line Credits: {line_credits}")
        
        # Calculate difference with proper rounding
        difference = currency.round(line_debits - line_credits)
        
        _logger.info(f"Difference: {difference}")
        
        # Handle rounding difference - use a more robust approach
        if not currency.is_zero(difference):
            # Get rounding difference account
            diff_account = self._get_rounding_difference_account(journal)
            
            # Determine which side needs adjustment
            if difference > 0:
                # Debits > Credits, need to add credit
                adjust_line = {
                    'account_id': diff_account.id,
                    'debit': 0.0,
                    'credit': abs(difference),
                    'currency_id': currency.id,
                    'amount_currency': 0.0,
                    'name': 'Rounding Adjustment',
                }
            else:
                # Credits > Debits, need to add debit
                adjust_line = {
                    'account_id': diff_account.id,
                    'debit': abs(difference),
                    'credit': 0.0,
                    'currency_id': currency.id,
                    'amount_currency': 0.0,
                    'name': 'Rounding Adjustment',
                }
            
            lines.append((0, 0, adjust_line))
            
            # Recalculate after adjustment
            final_debits = sum(line[2]['debit'] for line in lines)
            final_credits = sum(line[2]['credit'] for line in lines)
            
            _logger.info(f"Final Debits: {final_debits}, Final Credits: {final_credits}")
            
            # Double check the balance
            if not currency.is_zero(final_debits - final_credits):
                _logger.error(f"Still unbalanced! Debits: {final_debits}, Credits: {final_credits}")
                raise ValidationError(_("Journal entry cannot be balanced. Please check the amounts."))
        
        # Create and post move
        try:
            move_vals = {
                'move_type': 'entry',
                'journal_id': journal.id,
                'date': fields.Date.today(),
                'ref': f"Donation Import {fields.Date.today()}",
                'line_ids': lines,
                'currency_id': currency.id,
            }
            
            move = self.env['account.move'].sudo().create(move_vals)
            
            # Validate balance before posting - check if move is balanced
            if not self._is_move_balanced(move):
                _logger.error(f"Journal entry {move.id} is not balanced before posting")
                # Check individual line balances
                for line in move.line_ids:
                    _logger.debug(f"Line: Account={line.account_id.code}, Debit={line.debit}, Credit={line.credit}")
                
                # Try to fix by ensuring all lines have currency
                for line in move.line_ids:
                    if not line.currency_id:
                        line.currency_id = currency.id
                
                # Recalculate
                move.line_ids._onchange_amount_currency()
                move._recompute_dynamic_lines(recompute_all_taxes=True)
                
            move.action_post()
            
            # Verify after posting
            if not self._is_move_balanced(move):
                raise ValidationError(_("Journal entry is not balanced after posting."))
                
            return move
            
        except Exception as e:
            _logger.error(f"Failed to create journal entry: {str(e)}")
            raise ValidationError(_("Failed to create journal entry: %s") % str(e))

    def _is_move_balanced(self, move):
        """Check if a journal move is balanced"""
        total_debit = sum(move.line_ids.mapped('debit'))
        total_credit = sum(move.line_ids.mapped('credit'))
        currency = move.currency_id or move.company_currency_id
        
        # Check if debits and credits are equal (with tolerance for rounding)
        difference = currency.round(total_debit - total_credit)
        
        _logger.debug(f"Move balance check: Debits={total_debit}, Credits={total_credit}, Difference={difference}")
        
        return currency.is_zero(difference)

    def _get_rounding_difference_account(self, journal):
        """Get rounding difference account with proper fallbacks"""
        # First try journal's default account
        if journal.default_account_id:
            return journal.default_account_id
        
        # Try company's difference account
        company = self.env.company
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
                    "Please configure a default account on journal '%s' or "
                    "set up a rounding difference account." % journal.name
                ))
        
        return diff_account

    # ---------------------- Validation ----------------------
    def _validate_accumulators(self, debit_accumulator, credit_accumulator, company_currency):
        """Validate that accumulators are balanced"""
        total_debit = company_currency.round(sum(v['debit_base'] for v in debit_accumulator.values()))
        total_credit = company_currency.round(sum(v['credit_base'] for v in credit_accumulator.values()))
        
        difference = company_currency.round(total_debit - total_credit)
        
        if not company_currency.is_zero(difference):
            _logger.warning(f"Accumulators unbalanced by {difference}. Debits: {total_debit}, Credits: {total_credit}")
            
            # Try to find which currency is causing the issue
            for (account_id, currency_id), vals in debit_accumulator.items():
                _logger.debug(f"Debit: Account={account_id}, Currency={currency_id}, Amount={vals['debit_base']}")
            
            for (account_id, currency_id, analytic_id), vals in credit_accumulator.items():
                _logger.debug(f"Credit: Account={account_id}, Currency={currency_id}, Analytic={analytic_id}, Amount={vals['credit_base']}")
        
        return difference