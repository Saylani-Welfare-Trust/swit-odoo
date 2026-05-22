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
    _description = 'API Donation Wizard (refactored & fixed)'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')

    picking_type_id = fields.Many2one('stock.picking.type', string="Picking Type", default=lambda self: self.env.ref('bn_import_donation.online_donation_stock_picking_type', raise_if_not_found=False).id)
    source_location_id = fields.Many2one(related='picking_type_id.default_location_src_id', string="Source Location", store=True)
    destination_location_id = fields.Many2one(related='picking_type_id.default_location_dest_id', string="Destination Location", store=True)

    def create_fetch_log(self, history_id, message, status, reason):
        """Helper to create fetch log entries"""
        self.env['fetch.log'].create({
            'fetch_history_id': history_id,
            'name': message,
            'status': status,
            'reason': reason
        })

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

        history = self.env['fetch.history'].create({
            'start_date': self.start_date,
            'end_date': self.end_date,
        })

        self.create_fetch_log(history.id, f"Initiating donation fetch.", 'Initiated', 'Fetch process started')

        donations_info = self._fetch_donations_from_api(auth_url, donate_url, company, base_url, origin_host, history)
        if not donations_info:
            self.create_fetch_log(
                history.id,
                f"No donations found for the given date range. {self.start_date} to {self.end_date}",
                'No Data',
                'No donations returned from API'
            )
            return True

        # Count normal vs qurbani records (logging only)
        total_records = len(donations_info)
        qurbani_records = [rec for rec in donations_info if rec.get('qurbani') is True]
        normal_records = [rec for rec in donations_info if rec.get('qurbani') is not True]

        self.create_fetch_log(
            history.id,
            "Donation Type Summary",
            "Summary",
            f"""
                ==============================
                API DONATION FETCH SUMMARY
                ==============================
                Total Records Fetched: {total_records}
                Qurbani Records: {len(qurbani_records)}
                Normal Donation Records: {len(normal_records)}
                ==============================
            """
        )

        # Prepare bulk data
        journal = self.env['account.journal'].search([('name', 'ilike', 'Bank')], limit=1)
        gateway_config = self.env['gateway.config'].search([('name', '=', 'Web API')], limit=1)
        company_currency = company.currency_id

        all_data = self._prefetch_all_data(donations_info, gateway_config, company_currency, history)

        result = self._process_donations_bulk(
            donations_info, journal, gateway_config, company_currency, all_data, history
        )

        if result.get('new_donations') and journal and result.get('accumulators'):
            move = self._create_grouped_journal_move(
                journal,
                result['accumulators']['debit'],
                result['accumulators']['credit'],
                company_currency,
                history
            )
            history.write({
                'journal_entry_id': move.id,
                'picking_id': result['picking_id'] if result.get('picking_id') else False,
            })

            if result['new_donations']:
                self.env['api.donation'].browse(result['new_donations']).write({
                    'fetch_history_id': history.id
                })

        self.create_fetch_log(history.id, f"Donation fetch and processing completed successfully.", 'Completed', 'All operations completed successfully')
        return True

    # ---------------------- Bulk API Operations ----------------------
    def _fetch_donations_from_api(self, auth_url, donate_url, company, base_url, origin_host, history):
        self.create_fetch_log(history.id, f"Start _fetch_donations_from_api", 'API Fetch', 'Starting to fetch donations from API')
        try:
            with requests.Session() as session:
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

                resp = session.post(donate_url, json=payload, timeout=60)
                resp.raise_for_status()
                data = resp.json()

                if not isinstance(data, dict) or 'donationsInfo' not in data:
                    self.env['fetch.log'].create({
                        'fetch_history_id': history.id,
                        'name': f"Invalid donations payload: {data}"
                    })
                    _logger.error('Invalid donations payload: %s', data)
                    raise ValidationError(_('Invalid Donations Info'))

                self.create_fetch_log(history.id, f"End _fetch_donations_from_api", 'API Fetch', f"Completed fetching donations. Total: {len(data.get('donationsInfo') or [])}")
                return data.get('donationsInfo') or []

        except requests.exceptions.RequestException as e:
            _logger.exception('API request error')
            raise ValidationError(_('API request failed: %s') % str(e))
        except ValueError as e:
            _logger.error('Invalid JSON response: %s', str(e))
            raise ValidationError(_('Invalid JSON received from API.'))

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

    # ---------------------- Bulk Data Pre-fetching ----------------------
    def _prefetch_all_data(self, donations_info, gateway_config, company_currency, history):
        self.create_fetch_log(history.id, f"Start _prefetch_all_data", 'Prefetching', 'Starting to prefetch all required data')

        unique_currencies = set()
        unique_import_ids = set()
        unique_country_codes = set()
        unique_mobiles = set()

        for info in donations_info:
            if info.get('_id'):
                unique_import_ids.add(info.get('_id'))
            if info.get('currency'):
                unique_currencies.add(info.get('currency'))

            donor = info.get('donor_details') or {}
            if donor.get('country'):
                unique_country_codes.add(donor.get('country'))
            if donor.get('phone'):
                mobile = donor.get('phone', '')[-10:] if donor.get('phone') else ''
                if mobile:
                    unique_mobiles.add(mobile)

        # Bulk fetch currencies
        currencies = self.env['res.currency'].search([('name', 'in', list(unique_currencies))])
        currency_by_name = {c.name.lower(): c for c in currencies}

        # Bulk fetch conversion rates (rate = company currency / foreign currency)
        conversion_rates = {}
        for currency in currencies:
            rate = 1.0
            if currency != company_currency:
                # Get the rate from currency to company currency
                rate_obj = currency.rate_ids.sorted('name', reverse=True)[:1]
                if rate_obj:
                    rate = rate_obj.company_rate or 1.0
            conversion_rates[currency.name.lower()] = rate

        # Bulk fetch countries
        countries = self.env['res.country'].search([('code', 'in', list(unique_country_codes))])
        country_by_code = {c.code: c.id for c in countries}

        # Bulk fetch existing donations
        existing_import_ids = set()
        if unique_import_ids:
            existing_records = self.env['api.donation'].search_read(
                [('import_id', 'in', list(unique_import_ids))],
                ['import_id']
            )
            existing_import_ids = {r['import_id'] for r in existing_records}

        # Bulk fetch existing partners
        partner_cache = {}
        if unique_mobiles:
            donor_category = self.env.ref('bn_profile_management.donor_partner_category', raise_if_not_found=False)
            existing_partners = self.env['res.partner'].search_read(
                [('mobile', 'in', list(unique_mobiles))],
                ['id', 'mobile', 'country_code_id', 'category_id']
            )
            for partner in existing_partners:
                if donor_category and donor_category.id in (partner.get('category_id') or []):
                    country_code_id = partner.get('country_code_id')
                    country_code_id = country_code_id[0] if country_code_id else False
                    key = (partner.get('mobile'), country_code_id)
                    partner_cache[key] = partner['id']

        # Gateway config lines
        gateway_currency_lines = {}
        if gateway_config:
            for line in gateway_config.gateway_config_currency_ids:
                currency_name = (line.currency_id.name or '').strip().lower()
                if currency_name:
                    gateway_currency_lines[currency_name] = line.account_id.id

        gateway_product_lines = {}
        if gateway_config:
            for line in gateway_config.gateway_config_line_ids:
                product_name = (line.name or '').strip().lower()
                if product_name:
                    gateway_product_lines[product_name] = {
                        'account_id': line.product_id.property_account_income_id.id,
                        'product_id': line.product_id.id,
                    }

        donor_category = self.env.ref('bn_profile_management.donor_partner_category', raise_if_not_found=False)
        individual_category = self.env.ref('bn_profile_management.individual_partner_category', raise_if_not_found=False)

        default_partner = self.env['res.partner'].search(
            [('primary_registration_id', '=', '2025-9999998-9')],
            limit=1
        )
        default_partner_id = default_partner.id if default_partner else False

        self.create_fetch_log(history.id, f"End _prefetch_all_data", 'Prefetching', 'Completed prefetching all data')
        return {
            'currency_by_name': currency_by_name,
            'conversion_rates': conversion_rates,
            'country_by_code': country_by_code,
            'existing_import_ids': existing_import_ids,
            'partner_cache': partner_cache,
            'gateway_currency_lines': gateway_currency_lines,
            'gateway_product_lines': gateway_product_lines,
            'donor_category_ids': [
                donor_category.id if donor_category else False,
                individual_category.id if individual_category else False
            ],
            'default_partner_id': default_partner_id,
        }

    # ---------------------- Bulk Processing ----------------------
    def _process_donations_bulk(self, donations_info, journal, gateway_config, company_currency, all_data, history):
        self.create_fetch_log(history.id, f"Start _process_donations_bulk", "Processing", "Starting to process donations in bulk")

        new_donation_ids = []
        debit_accumulator = defaultdict(lambda: {'debit_base': 0.0, 'amount_currency': 0.0})
        credit_accumulator = defaultdict(lambda: {'credit_base': 0.0, 'amount_currency': 0.0})

        StockPicking = self.env['stock.picking']
        StockMove = self.env['stock.move']
        stock_accumulator = defaultdict(float)

        # Counters for debugging
        total_records = 0
        skipped_records = 0
        processed_records = 0

        partner_to_create = []
        partner_mapping = {}

        donations_to_create = []

        for info_idx, info in enumerate(donations_info):
            total_records += 1
            import_id = info.get('_id')

            if not import_id or import_id in all_data['existing_import_ids']:
                skipped_records += 1
                self.create_fetch_log(
                    history.id,
                    f"Skipping donation with import_id {import_id} (already exists or missing)",
                    'Skipped',
                    f"Donation with import_id {import_id} is skipped"
                )
                continue

            processed_records += 1

            donation_vals = self._prepare_donation_vals_fast(
                info,
                all_data,
                info_idx,
                partner_to_create,
                partner_mapping,
                history
            )

            if donation_vals:
                donations_to_create.append(donation_vals)

                if gateway_config and journal:
                    self._accumulate_donation_lines_fast(
                        donation_vals,
                        all_data,
                        company_currency,
                        debit_accumulator,
                        credit_accumulator,
                        history
                    )

            # Stock processing
            items = info.get('items') or []
            for it in items:
                item_name = ''
                item_data = it.get('item', {})
                if isinstance(item_data, dict) and 'en' in item_data:
                    item_name = item_data.get('en', {}).get('name', '')
                normalized_item_name = (item_name or '').strip().lower()

                product_line = gateway_config.gateway_config_line_ids.filtered(
                    lambda l: (l.name or '').strip().lower() == normalized_item_name
                )
                product = product_line.product_id if product_line else False

                if product and product.detailed_type == 'product':
                    qty = float(it.get('qty') or 1.0)
                    stock_accumulator[product.id] += qty

        # ----- Partner creation (deduplicated) -----
        seen = set()
        unique_partners = []
        for vals in partner_to_create:
            key = (vals.get('mobile'), vals.get('country_code_id'))
            if key not in seen:
                seen.add(key)
                unique_partners.append(vals)

        partners_to_create_final = []
        for vals in unique_partners:
            existing = self.env['res.partner'].search([
                '|',
                ('email', '=', vals.get('email')),
                ('mobile', '=', vals.get('mobile')),
            ], limit=1)
            if not existing:
                if not vals.get('name'):
                    self.create_fetch_log(history.id, f"Skipping partner with missing name", 'Warning', str(vals))
                    continue
                if not vals.get('mobile') and not vals.get('email'):
                    self.create_fetch_log(history.id, f"Skipping partner with no contact", 'Warning', str(vals))
                    continue
                partners_to_create_final.append(vals)
            else:
                # Already exists: map it now
                partner_mapping[(vals.get('mobile'), vals.get('country_code_id'))] = existing.id

        created_partners = self.env['res.partner']
        if partners_to_create_final:
            try:
                created_partners = self.env['res.partner'].create(partners_to_create_final)
                for idx, vals in enumerate(partners_to_create_final):
                    if idx < len(created_partners):
                        partner_mapping[(vals.get('mobile'), vals.get('country_code_id'))] = created_partners[idx].id
                try:
                    created_partners.action_register()
                except Exception as reg_err:
                    _logger.warning(f"Partner registration error: {reg_err}")
            except Exception as create_err:
                _logger.exception("Partner creation failed")
                raise ValidationError(f"Failed to create partners: {create_err}")

        # Link donors to donations
        donations_with_partner = 0
        donations_without_partner = 0
        for donation_val in donations_to_create:
            if 'partner_key' in donation_val:
                partner_id = partner_mapping.get(donation_val['partner_key'])
                if partner_id:
                    donation_val['donor_id'] = partner_id
                    donations_with_partner += 1
                else:
                    donations_without_partner += 1
                del donation_val['partner_key']
            else:
                if donation_val.get('donor_id'):
                    donations_with_partner += 1
                else:
                    donations_without_partner += 1

        # Create donations
        if donations_to_create:
            new_donations = self.env['api.donation'].create(donations_to_create)
            new_donation_ids = new_donations.ids

        # Create stock picking
        picking = False
        if stock_accumulator:
            picking_type = self.picking_type_id
            if not picking_type:
                raise ValidationError(_("Stock Picking Type is missing."))
            picking = StockPicking.create({
                'picking_type_id': picking_type.id,
                'location_id': self.source_location_id.id,
                'location_dest_id': self.destination_location_id.id,
                'origin': f"API Donation {fields.Date.today()}",
            })
            for product_id, qty in stock_accumulator.items():
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

        self.create_fetch_log(history.id, f"End _process_donations_bulk", 'Processing', 'Completed bulk processing')
        return {
            'new_donations': new_donation_ids,
            'accumulators': {
                'debit': dict(debit_accumulator),
                'credit': dict(credit_accumulator)
            },
            'picking_id': picking.id if picking else False
        }

    def _prepare_donation_vals_fast(self, info, all_data, info_idx, partner_to_create, partner_mapping, history):
        if info.get('status') != 'success':
            return None

        created_dt = self._parse_iso_to_dt_fast(info.get('createdAt'), history)
        updated_dt = self._parse_iso_to_dt_fast(info.get('updatedAt'), history)

        currency_name = info.get('currency', '') or ''
        conv_rate = all_data['conversion_rates'].get(currency_name.lower(), 1.0)

        if currency_name.lower() and currency_name.lower() not in all_data['currency_by_name']:
            self.create_fetch_log(history.id, f"Currency {currency_name} not found, using company currency", 'Error', '')
            currency_name = self.env.company.currency_id.name.lower()
            conv_rate = 1.0

        total_amount = float(info.get('total_amount', 0) or 0) - float(info.get('bank_charges', 0) or 0)
        total_local = total_amount * conv_rate

        donor = info.get('donor_details') or {}
        donor_id = None
        partner_key = None

        if donor.get('name', ''):
            mobile = donor.get('phone', '')[-10:] if donor.get('phone') else ''
            country_code = donor.get('country', '')
            country_id = all_data['country_by_code'].get(country_code)

            if mobile and country_id:
                for cached_key, cached_id in all_data['partner_cache'].items():
                    if cached_key[0] == mobile and cached_key[1] == country_id:
                        donor_id = cached_id
                        break

            if not donor_id:
                partner_vals = {
                    'name': donor.get('name', ''),
                    'mobile': mobile,
                    'email': donor.get('email', ''),
                    'country_code_id': country_id,
                    'category_id': [(6, 0, [cid for cid in all_data['donor_category_ids'] if cid])],
                }
                partner_to_create.append(partner_vals)
                partner_key = (mobile, country_id)
        else:
            donor_id = all_data['default_partner_id']

        orm_items = []
        order_lines = []
        for it in info.get('items') or []:
            types_name = ''
            item_name = ''
            type_data = it.get('type', {})
            if isinstance(type_data, dict) and 'en' in type_data:
                types_name = type_data.get('en', {}).get('name', '')
            item_data = it.get('item', {})
            if isinstance(item_data, dict) and 'en' in item_data:
                item_name = item_data.get('en', {}).get('name', '')

            if info.get('qurbani') != True:
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
            else:
                # Qurbani processing with safe share_names handling
                product_key = (
                    f"{info.get('donationType', '')}"
                    f"{item_name}"
                    f"{types_name}"
                ).strip().lower()
                config = all_data['gateway_product_lines'].get(product_key)
                product = self.env['product.product'].browse(config['product_id']) if config else False
                quantity = int(it.get('qty', 1) or 1)
                amount = float(it.get('price', 0) or 0)
                day_name = it.get('day', '')
                city_name = it.get('qurbaniCity', '')
                branch_name = it.get('qurbaniBranch', '')
                qurbani_fullfilment = it.get('qurbaniFulfillment', '')

                # SAFE share_names handling – fix for ZeroDivisionError
                share_names = it.get('share_names')
                if not share_names:  # None or empty list
                    share_names = [donor.get('name', 'Anonymous')]
                elif isinstance(share_names, str):
                    share_names = [share_names]
                elif not isinstance(share_names, list):
                    share_names = [donor.get('name', 'Anonymous')]

                for idx in range(quantity):
                    share_name = share_names[idx % len(share_names)]
                    hissa_name = f"{idx + 1}. {share_name}" if quantity > 1 else share_name
                    line_vals = {
                        'product_id': product.id if product else False,
                        'quantity': 1,
                        'amount': amount,
                        'day': day_name if day_name else False,
                        'city': city_name if city_name else False,
                        'hissa_name': hissa_name,
                        'branch': branch_name if branch_name else False,
                        'qurbani_fullfilment': qurbani_fullfilment if qurbani_fullfilment else False,
                    }
                    order_lines.append([0, 0, line_vals])

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
            'qurbani_order_line_ids': order_lines,
            'fetch_history_id': history.id,
            'qurbani': True if info.get('qurbani') == True else False,
        }

        if donor_id:
            donation_vals['donor_id'] = donor_id
        elif partner_key is not None:
            donation_vals['partner_key'] = partner_key
        else:
            donation_vals['donor_id'] = all_data['default_partner_id']

        return donation_vals

    def _accumulate_donation_lines_fast(self, donation_vals, all_data, company_currency,
                                        debit_accumulator, credit_accumulator, history):
        currency_name = donation_vals.get('currency', '')
        currency_rec = all_data['currency_by_name'].get(currency_name.lower())
        if not currency_rec:
            _logger.warning(f"Currency {currency_name} not found for donation")
            return

        debit_account_id = all_data['gateway_currency_lines'].get(currency_name.lower())
        if not debit_account_id:
            _logger.warning(f"Debit account not found for currency {currency_name}")
            return

        is_foreign = currency_rec != company_currency
        conv_rate = donation_vals.get('conversion_rate', 1.0)
        if conv_rate <= 0:
            _logger.warning(f"Invalid conversion rate {conv_rate} for currency {currency_name}")
            return

        for it in donation_vals.get('donation_item_ids', []):
            item = it[2]  # (0,0,values)
            product_name = (
                f"{item.get('donation_type', '')}"
                f"{item.get('item', '')}"
                f"{item.get('type', '')}"
            ).strip().lower()

            config = all_data['gateway_product_lines'].get(product_name)
            if not config:
                _logger.warning(f"Product config not found for {product_name}")
                continue

            credit_account_id = config['account_id']
            if not credit_account_id:
                _logger.warning(f"No account_id for product {product_name}")
                continue

            item_total_foreign = float(item.get('total', 0.0))

            # FIX 1: Convert foreign to company currency using multiplication
            item_total_base = item_total_foreign * conv_rate
            # FIX 2: Round after conversion, using company currency rounding
            item_total_base = company_currency.round(item_total_base)

            # Foreign amount for amount_currency field (always positive)
            if is_foreign:
                foreign_amount = currency_rec.round(item_total_foreign)
            else:
                foreign_amount = item_total_base

            # FIX 3: Use positive amount_currency for both debit and credit
            # Debit line (cash/bank account)
            debit_key = (debit_account_id, currency_rec.id if is_foreign else company_currency.id)
            d = debit_accumulator[debit_key]
            d['debit_base'] += item_total_base
            if is_foreign:
                d['amount_currency'] += foreign_amount  # positive

            # Credit line (income account)
            credit_key = (credit_account_id, currency_rec.id if is_foreign else company_currency.id)
            c = credit_accumulator[credit_key]
            c['credit_base'] += item_total_base
            if is_foreign:
                c['amount_currency'] += foreign_amount  # positive, NOT negative

    # ---------------------- Helper Methods ----------------------
    def _date_to_iso_z(self, date_val):
        if not date_val:
            return None
        dt = datetime.combine(date_val, time.min).replace(tzinfo=timezone.utc)
        return dt.isoformat(timespec='milliseconds').replace('+00:00', 'Z')

    def _parse_iso_to_dt_fast(self, iso_str, history):
        if not iso_str:
            return None
        try:
            if 'T' in iso_str:
                if 'Z' in iso_str:
                    return datetime.fromisoformat(iso_str.replace('Z', '+00:00')).replace(tzinfo=None)
                elif '+' in iso_str or '-' in iso_str[10:]:
                    return datetime.fromisoformat(iso_str).replace(tzinfo=None)
                else:
                    return datetime.fromisoformat(iso_str)
            else:
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d']:
                    try:
                        return datetime.strptime(iso_str, fmt)
                    except ValueError:
                        continue
                return datetime.strptime(iso_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
        except Exception:
            _logger.debug('Failed to parse datetime: %s', iso_str)
            return None

    # ---------------------- Journal Entry Creation ----------------------
    def _create_grouped_journal_move(self, journal, debit_accumulator, credit_accumulator, company_currency, history):
        lines = []
        company_currency_id = company_currency.id

        # Debit lines
        for (account_id, currency_id), vals in debit_accumulator.items():
            debit_amount = company_currency.round(vals['debit_base'])
            if not debit_amount:
                continue

            if currency_id == company_currency_id:
                lines.append((0, 0, {
                    'account_id': account_id,
                    'debit': debit_amount,
                    'credit': 0.0,
                    'name': 'Donation Import - Debit',
                }))
            else:
                # Foreign currency debit line: amount_currency must be positive
                lines.append((0, 0, {
                    'account_id': account_id,
                    'debit': debit_amount,
                    'credit': 0.0,
                    'currency_id': currency_id,
                    'amount_currency': abs(vals['amount_currency']),  # positive
                    'name': 'Donation Import - Debit',
                }))

        # Credit lines
        for (account_id, currency_id), vals in credit_accumulator.items():
            credit_amount = company_currency.round(vals['credit_base'])
            if not credit_amount:
                continue

            if currency_id == company_currency_id:
                lines.append((0, 0, {
                    'account_id': account_id,
                    'debit': 0.0,
                    'credit': credit_amount,
                    'name': 'Donation Import - Credit',
                }))
            else:
                # Foreign currency credit line: amount_currency must be NEGATIVE
                lines.append((0, 0, {
                    'account_id': account_id,
                    'debit': 0.0,
                    'credit': credit_amount,
                    'currency_id': currency_id,
                    'amount_currency': -abs(vals['amount_currency']),  # negative
                    'name': 'Donation Import - Credit',
                }))

        if not lines:
            self.create_fetch_log(history.id, "No journal lines to create.", 'Error', "No journal lines to create.")
            return None

        # Balance check
        total_debit = sum(l[2]['debit'] for l in lines)
        total_credit = sum(l[2]['credit'] for l in lines)
        diff = company_currency.round(total_debit - total_credit)

        if not company_currency.is_zero(diff):
            diff_account = self._get_rounding_difference_account(journal, history)
            if diff_account:
                if diff > 0:
                    lines.append((0, 0, {
                        'account_id': diff_account.id,
                        'debit': 0.0,
                        'credit': abs(diff),
                        'name': 'Rounding Adjustment',
                    }))
                else:
                    lines.append((0, 0, {
                        'account_id': diff_account.id,
                        'debit': abs(diff),
                        'credit': 0.0,
                        'name': 'Rounding Adjustment',
                    }))

        move = self.env['account.move'].sudo().create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': fields.Date.today(),
            'ref': f"Donation Import {fields.Date.today()}",
            'line_ids': lines,
        })
        # move.action_post()   # uncomment if you want to post immediately
        return move

    def _get_rounding_difference_account(self, journal, history):
        if journal.default_account_id:
            return journal.default_account_id

        company = self.env.company
        if company.difference_account_prefix:
            diff_account = self.env['account.account'].search([
                ('code', 'like', f"{company.difference_account_prefix}%"),
                ('company_id', '=', company.id)
            ], limit=1)
            if diff_account:
                return diff_account

        diff_account = self.env['account.account'].search([
            ('account_type', 'in', ['expense', 'income']),
            ('name', 'ilike', 'rounding'),
            ('company_id', '=', company.id)
        ], limit=1)

        if not diff_account:
            diff_account = self.env['account.account'].search([
                ('account_type', '=', 'expense'),
                ('company_id', '=', company.id)
            ], limit=1)

        return diff_account