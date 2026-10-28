from odoo import models, fields, _
from odoo.exceptions import ValidationError
from datetime import datetime, time, timezone, timedelta
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
        default=lambda self: self._default_picking_type_id()
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

    # Pages requested from the API, and days fetched again by the daily cron
    # (already imported donations are skipped, so a missed run is caught up).
    PER_PAGE = 50
    CRON_DAYS_BACK = 3

    def _default_picking_type_id(self):
        return self.env['stock.warehouse']._bn_get_program_type('online_donation').id

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
    # ENTRY POINT (NOW PER PAGE HISTORY)
    # =========================================================
    def action_fetch_donation(self):
        if not self:
            # Daily cron "Fetch Donation Data": it calls this on the empty model.
            return self.create({}).action_fetch_donation()
        self.ensure_one()

        today = fields.Date.today()

        if self.start_date and self.end_date:
            start_date = self.start_date
            end_date = self.end_date
        else:
            # Without dates (cron): the last days up to yesterday. Donations
            # already imported are skipped, so a missed run is caught up.
            start_date = today - timedelta(days=self.CRON_DAYS_BACK)
            end_date = today - timedelta(days=1)

        if start_date and end_date and start_date > end_date:
            raise ValidationError(_("Start Date must be earlier than or equal to End Date."))

        # The credentials are readable by the Import Donation Admin only.
        company = self.env.company.sudo()
        if not (company.url and company.client_id and company.client_secret):
            raise ValidationError(_(
                "The Donation API is not configured: set its URL, Client ID and Client Secret on the "
                "company (Settings > Companies > Donation API)."))

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
        origin_host = urlparse(base_url).hostname or ''

        auth_url = f"{company.url.rstrip('/')}/api/odoo/auth"
        donate_url = f"{company.url.rstrip('/')}/api/odoo/donationInfo"

        page = 1
        per_page = self.PER_PAGE
        while True:

            # =========================================================
            # 🔥 CREATE NEW HISTORY FOR EACH PAGE
            # =========================================================
            history = self.env['fetch.history'].create({
                'start_date': start_date,
                'end_date': end_date,
                'page': page,
                'per_page': per_page,
            })

            self.create_fetch_log(history.id, f"Starting Page {page}", "Initiated", "Page-wise fetch started")

            payload = {
                "status": "success",
                "page": page,
                "perPage": per_page,
            }

            if start_date:
                payload["startDate"] = self._date_to_iso_z(start_date, time.min)

            if end_date:
                payload["endDate"] = self._date_to_iso_z(end_date, time(23, 59, 59))

            page_data = self._fetch_donations_from_api(
                auth_url,
                donate_url,
                company,
                base_url,
                origin_host,
                history,
                override_payload=payload
            )

            if not page_data:
                if page > 1:
                    # The previous page was the last one: no empty history.
                    history.sudo().unlink()
                else:
                    self.create_fetch_log(history.id, "No donations in this period", "Done", "Nothing to import")
                break

            # =========================================================
            # PROCESS THIS PAGE ONLY
            # =========================================================
            self._process_single_page(page_data, history, company)

            # stop condition
            if len(page_data) < per_page:
                break

            page += 1

        return True

    # =========================================================
    # PAGE PROCESSOR (WRAPPER OVER YOUR EXISTING LOGIC)
    # =========================================================
    def _process_single_page(self, donations_info, history, company):

        self.create_fetch_log(history.id, "Processing page data", "Processing", f"Records: {len(donations_info)}")

        journal = self.env['account.journal'].search(
            [('type', '=', 'bank'), ('company_id', '=', company.id)], limit=1)
        gateway_config = self.env['gateway.config'].search([('name', '=', 'Web API')], limit=1)
        if not gateway_config:
            gateway_config = self.env['gateway.config'].search([('type', '=', 'api')], limit=1)
        if not gateway_config:
            self.create_fetch_log(history.id, "No API gateway configuration ('Web API')", "Error",
                                  "Donations are stored without journal entry or stock transfer")
        company_currency = company.currency_id

        all_data = self._prefetch_all_data(donations_info, gateway_config, company_currency, history)

        result = self._process_donations_bulk(
            donations_info,
            journal,
            gateway_config,
            company_currency,
            all_data,
            history
        )

        if result.get('new_donations') and journal and result['accumulators']['credit']:
            move = self._create_grouped_journal_move(
                journal,
                result['accumulators']['debit'],
                result['accumulators']['credit'],
                company_currency,
                history
            )

            history.write({'journal_entry_id': move.id})
        if result.get('picking_id'):
            history.write({'picking_id': result['picking_id']})

        self.create_fetch_log(history.id, "Page Completed", "Done", "Page processing finished")

        return result

    # =========================================================
    # API CALL
    # =========================================================
    def _fetch_donations_from_api(
        self, auth_url, donate_url, company,
        base_url, origin_host, history,
        override_payload=None
    ):
        try:
            with requests.Session() as session:

                session.headers.update({
                    'Origin': base_url,
                    'x-forwarded-for': origin_host,
                    'Content-Type': 'application/json',
                })

                token = self._authenticate(
                    session,
                    auth_url,
                    company.client_id,
                    company.client_secret
                )

                session.headers.update({
                    'authorization': f'bearer {token}'
                })

                payload = override_payload or {"status": "success"}

                resp = session.post(donate_url, json=payload, timeout=60)
                resp.raise_for_status()

                data = resp.json()

                if not isinstance(data, dict) or 'donationsInfo' not in data:
                    raise ValidationError(_("Invalid Donations Info"))

                return data.get('donationsInfo') or []

        except Exception as e:
            raise ValidationError(_('API Error: %s') % str(e))

    # =========================================================
    # EVERYTHING BELOW REMAINS YOUR ORIGINAL CODE
    # =========================================================
    # (UNCHANGED - your full logic stays exactly same)

    def _authenticate(self, session, url, client_id, client_secret):
        resp = session.post(url, json={
            "ClientID": client_id,
            "ClientSecret": client_secret
        }, timeout=30)
        resp.raise_for_status()
        token = resp.json().get('token')
        if not token:
            raise ValidationError(_("Token missing"))
        return token

    # ---------------------- Bulk Data Pre-fetching ----------------------
    def _prefetch_all_data(self, donations_info, gateway_config, company_currency, history):
        self.create_fetch_log(history.id, f"Start _prefetch_all_data", 'Prefetching', 'Starting to prefetch all required data for processing')

        """Prefetch all required data in bulk to minimize database queries"""
        # Extract all unique values for bulk queries
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

        self.create_fetch_log(history.id, f"Unique Currencies: {unique_currencies}, Unique Country Codes: {unique_country_codes}, Unique Mobiles: {unique_mobiles}, Unique Import IDs: {unique_import_ids}", 'Prefetching', 'Extracted unique values for bulk data fetching')

        # Bulk fetch currencies
        currencies = self.env['res.currency'].search(
            [('name', 'in', [name.upper() for name in unique_currencies])])
        currency_by_name = {c.name.lower(): c for c in currencies}
        currency_by_name.setdefault(company_currency.name.lower(), company_currency)

        # Bulk fetch conversion rates
        conversion_rates = {}
        for currency in currencies:
            if currency.rate_ids:
                latest_rate = currency.rate_ids.sorted('name', reverse=True)[0]
                conversion_rates[currency.name.lower()] = float(latest_rate.company_rate or 1.0)
            else:
                conversion_rates[currency.name.lower()] = 1.0

        self.create_fetch_log(history.id, f"Conversion Rates: {conversion_rates}", 'Prefetching', 'Fetched conversion rates for currencies')
        
        # Bulk fetch countries
        countries = self.env['res.country'].search([('code', 'in', list(unique_country_codes))])
        country_by_code = {c.code: c.id for c in countries}
        
        # Bulk fetch existing donations to avoid duplicates
        existing_import_ids = set()
        if unique_import_ids:
            existing_records = self.env['api.donation'].search_read(
                [('import_id', 'in', list(unique_import_ids))], 
                ['import_id']
            )
            existing_import_ids = {r['import_id'] for r in existing_records}
        
        self.create_fetch_log(history.id, f"Existing Import IDs: {existing_import_ids}", 'Prefetching', 'Fetched existing import IDs to avoid duplicates')

        # Bulk fetch existing partners - SIMPLER AND SAFER APPROACH
        partner_cache = {}
        if unique_mobiles:
            # Get donor category
            donor_category = self.env.ref('bn_profile_management.donor_partner_category', raise_if_not_found=False)
            
            # Search partners by mobile number
            existing_partners = self.env['res.partner'].search_read(
                [('mobile', 'in', list(unique_mobiles))],
                ['id', 'mobile', 'country_code_id', 'category_id']
            )
            
            # Filter to only include donors and cache them
            for partner in existing_partners:
                if donor_category and donor_category.id in (partner.get('category_id') or []):
                    country_code_id = partner.get('country_code_id')
                    country_code_id = country_code_id[0] if country_code_id else False
                    key = (partner.get('mobile'), country_code_id)
                    partner_cache[key] = partner['id']
        
        self.create_fetch_log(history.id, f"Partner Cache: {partner_cache}", 'Prefetching', 'Fetched partner cache for existing donors')

        # Pre-fetch gateway config data
        gateway_currency_lines = {}
        if gateway_config:
            for line in gateway_config.gateway_config_currency_ids:

                currency_name = (line.currency_id.name or '').strip().lower()

                if not currency_name:
                    continue

                gateway_currency_lines[currency_name] = line.account_id.id
        self.create_fetch_log(history.id, f"Gateway Currency Lines: {gateway_currency_lines}", 'Prefetching', 'Fetched gateway currency lines')

        gateway_product_lines = {}
        if gateway_config:
            for line in gateway_config.gateway_config_line_ids:

                product_name = (line.name or '').strip().lower()

                if not product_name:
                    continue

                gateway_product_lines[product_name] = {
                    'account_id': line.product_id.property_account_income_id.id,
                    'product_id': line.product_id.id,
                }
        # Get donor category IDs
        donor_category = self.env.ref('bn_profile_management.donor_partner_category', raise_if_not_found=False)
        individual_category = self.env.ref('bn_profile_management.individual_partner_category', raise_if_not_found=False)
        
        # Default partner for missing donors
        default_partner_id = gateway_config.default_partner_id.id if gateway_config else False
        
        self.create_fetch_log(history.id, f"End _prefetch_all_data", 'Prefetching', 'Completed prefetching all required data for processing')

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
            'bank_charges_account_id': gateway_config.bank_charges_account_id.id if gateway_config else False,
            'company_currency': company_currency,
        }

    # ---------------------- Bulk Processing ----------------------
    # ---------------------- TESTING / DEBUG COUNTERS ----------------------

    def _process_donations_bulk(self, donations_info, journal, gateway_config, company_currency, all_data, history):
        self.create_fetch_log(
            history.id,
            f"Start _process_donations_bulk",
            "Processing",
            "Starting to process donations in bulk - NO partner creation, just store records"
        )

        new_donation_ids = []
        debit_accumulator = defaultdict(lambda: {'debit_base': 0.0, 'amount_currency': 0.0})
        credit_accumulator = defaultdict(lambda: {'credit_base': 0.0, 'amount_currency': 0.0})

        StockPicking = self.env['stock.picking']
        StockMove = self.env['stock.move']

        stock_accumulator = defaultdict(float)
        
        total_records = 0
        skipped_records = 0
        processed_records = 0

        # DEBUG: track full record data for already-synced vs newly seen donations
        already_synced_records = []
        new_records = []

        donations_to_create = []

        for info_idx, info in enumerate(donations_info):
            total_records += 1
            import_id = info.get('_id')

            if not import_id or import_id in all_data['existing_import_ids']:
                skipped_records += 1
                already_synced_records.append(info)
                self.create_fetch_log(
                    history.id,
                    f"Skipping donation with import_id {import_id} (already exists or missing)",
                    'Skipped',
                    f"Donation with import_id {import_id} is skipped because it already exists or is missing"
                )
                continue

            processed_records += 1
            new_records.append(info)

            # Prepare donation values WITHOUT partner creation
            donation_vals = self._prepare_donation_vals_fast_no_partner(
                info,
                all_data,
                info_idx,
                history
            )

            if not donation_vals:
                # Unsuccessful payment: nothing is stored, booked or delivered.
                continue

            if gateway_config and journal:
                self._accumulate_donation_lines_fast(
                    donation_vals,
                    all_data,
                    company_currency,
                    debit_accumulator,
                    credit_accumulator,
                    history
                )
            else:
                donation_vals.update({
                    'journal_status': 'not_in_entry',
                    'journal_note': _('No bank journal or no API gateway configuration.'),
                })
            donations_to_create.append(donation_vals)

            # STOCK: same product mapping as the journal entry
            for it in info.get('items') or []:
                config = self._resolve_product(all_data, *self._item_names(it))
                product = self.env['product.product'].browse(config['product_id']) if config else False
                if product and product.detailed_type == 'product':
                    qty = float(it.get('qty') or 1.0)
                    stock_accumulator[product.id] += qty

        # CREATE DONATIONS IN BULK - Just store them, no partner creation
        if donations_to_create:
            new_donations = self.env['api.donation'].create(donations_to_create)
            new_donation_ids = new_donations.ids
            
            self.create_fetch_log(
                history.id,
                f"✓ Created {len(new_donation_ids)} donation records without partner assignment",
                'Success',
                f"Donation IDs: {new_donation_ids}"
            )

        # STOCK PICKING (unchanged)
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
            picking.with_context(skip_backorder=True, skip_immediate=True).button_validate()
            if picking.state != 'done':
                self.create_fetch_log(
                    history.id,
                    f"Stock transfer {picking.name} could not be validated (status: {picking.state})",
                    'Error',
                    'button_validate did not complete the transfer automatically'
                )

        self.create_fetch_log(
            history.id,
            f"End _process_donations_bulk - Summary: Total={total_records}, Skipped={skipped_records}, Processed={processed_records}",
            'Processing',
            'Completed bulk donation processing without partner creation'
        )

        return {
            'new_donations': new_donation_ids,
            'accumulators': {
                'debit': dict(debit_accumulator),
                'credit': dict(credit_accumulator)
            },
            'picking_id': picking.id if picking else False,
            # DEBUG: full record data, used to build the page-by-page sync report
            'already_synced_records': already_synced_records,
            'new_records': new_records,
        }
        
    def _prepare_donation_vals_fast_no_partner(self, info, all_data, info_idx, history):
        """Prepare donation values WITHOUT partner creation - just store donor info as text"""
        
        if info.get('status') != 'success':
            self.create_fetch_log(
                history.id,
                f"Skipping donation at index {info_idx} due to unsuccessful status",
                'Skipped',
                f"Donation status is not successful"
            )
            return None
        
        # Parse dates
        created_dt = self._parse_iso_to_dt_fast(info.get('createdAt'), history)
        updated_dt = self._parse_iso_to_dt_fast(info.get('updatedAt'), history)
        
        # Get currency and the conversion rate of the donation's date
        currency_name = info.get('currency', '') or ''
        currency_rec = all_data['currency_by_name'].get(currency_name.lower())
        company_currency = all_data['company_currency']
        conv_rate = 1.0
        if currency_rec and currency_rec != company_currency:
            rate_date = (created_dt or datetime.now()).date()
            conv_rate = company_currency._get_conversion_rate(
                company_currency, currency_rec, self.env.company, rate_date) or 1.0
        
        if not currency_name:
            currency_name = company_currency.name
        elif currency_name.lower() not in all_data['currency_by_name']:
            # Never book a foreign amount as company currency: the donation is
            # stored and flagged "Not in Journal Entry" (see the accumulation).
            self.create_fetch_log(
                history.id,
                f"Currency {currency_name} is not active in Odoo",
                'Error',
                "The donation is stored but left out of the journal entry"
            )
        
        # Calculate amounts
        total_amount = float(info.get('total_amount', 0) or 0) - float(info.get('bank_charges', 0) or 0)
        total_local = total_amount / conv_rate
        
        # DONOR INFO - Just store as text, don't create partner
        donor = info.get('donor_details') or {}
        
        # Process donation items
        items = info.get('items') or []
        orm_items = []
        order_lines = []
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
            
            else:   # qurbani == True
                # -------------------------------------------------------------
                # 1. Product resolution (from your upper code)
                # -------------------------------------------------------------
                self.create_fetch_log(
                    history.id,
                    f"Distribution Data from API",
                    "Qurbani",
                    f"Qurbani json {info}"
                )

                # -------------------------------------------------------------
                # 2. Share names (from upper code)
                # -------------------------------------------------------------
                share_names = it.get('share_names', [donor.get('name', '')])
                if not share_names:
                    share_names = [donor.get('name', '')]

                # -------------------------------------------------------------
                # 3. Create qurbani order lines (from upper code)
                # -------------------------------------------------------------
                # FIXED: number of lines should follow the number of share
                # names actually provided, not `qty` - a "Full - 7 Shares"
                # item can have qty=2 (2 units bought) but 14 share_names
                # (2 x 7 shares). Using qty here silently dropped shares.
                item_qty = int(it.get('qty', 1) or 1)
                num_lines = len(share_names)
                if num_lines != item_qty:
                    self.create_fetch_log(
                        history.id,
                        f"Qurbani share count mismatch for item '{item_name}': "
                        f"qty={item_qty} but {num_lines} share_names provided. "
                        f"Using share_names count ({num_lines}) to build order lines.",
                        'Warning',
                        'qty vs share_names length mismatch'
                    )

                item_total = float(it.get('total', 0) or 0)
                # FIXED: previously each generated line carried the item's
                # full total, so summing `total` across lines double/multi
                # counted the amount. Split evenly across the actual lines.
                per_line_total = item_total / num_lines if num_lines else item_total

                for idx in range(num_lines):
                    share_name = share_names[idx % len(share_names)]

                    order_lines.append({
                        'donation_type': it.get('donationType', ''),
                        'total': per_line_total,
                        'price': it.get('price', 0),
                        'price_id': it.get('price_id', 0),
                        'qty': 1,
                        'type': types_name,
                        'item': item_name,
                        'donation_no': it.get('donationNo', 0),
                        'day': it.get('day', ''),
                        # City now sourced from donor_details.qurbaniCity
                        # (donation-level city) instead of the item's own
                        # 'city' key.
                        'city': donor.get('qurbaniCity', ''),
                        'hissa_name': share_name,
                        'branch': it.get('qurbaniBranch', ''),
                        'qurbani_fullfilment': it.get('qurbaniFulfillment', ''),
                    })


        self.create_fetch_log(history.id, f"orm_items for donation at index {info_idx}: {orm_items}", 'Processing', f"Prepared ORM items for donation at index {info_idx}")
        self.create_fetch_log(history.id, f"order_lines for donation at index {info_idx}: {order_lines}", 'Processing', f"Prepared Order lines for donation at index {info_idx}")

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
            'qurbani_order_line_ids': [(0, 0, it) for it in order_lines],
            'fetch_history_id': history.id,
            'qurbani': True if info.get('qurbani') else False,
        }

        return donation_vals
          
    def _accumulate_donation_lines_fast(self, donation_vals, all_data, company_currency,
                                        debit_accumulator, credit_accumulator, history):
        """Add one donation to the page's journal entry:
          Cr income account of each mapped item ........ gross item total
          Dr gateway account of the currency ............ gross - bank charges
          Dr Bank Charges Account of the gateway ........ bank charges
        Items that are not mapped (or whose product has no income account) are
        left out; the donation then says so in its Accounting status/note."""
        import_id = donation_vals.get('import_id', '')
        notes = []

        def done(status):
            donation_vals['journal_status'] = status
            donation_vals['journal_note'] = '\n'.join(notes) or False
            if notes:
                self.create_fetch_log(history.id, f"Donation {import_id}: " + ' | '.join(notes),
                                      'Error' if status != 'in_entry' else 'Warning', 'Journal entry')

        currency_name = donation_vals.get('currency', '') or ''
        currency_rec = all_data['currency_by_name'].get(currency_name.lower())
        if not currency_rec:
            notes.append(_('Currency "%s" is not active in Odoo.') % currency_name)
            return done('not_in_entry')

        debit_account_id = all_data['gateway_currency_lines'].get(currency_name.lower())
        if not debit_account_id:
            notes.append(_('No debit account for currency %s on the API gateway configuration.') % currency_rec.name)
            return done('not_in_entry')

        is_foreign = currency_rec != company_currency
        conv_rate = float(donation_vals.get('conversion_rate') or 1.0) or 1.0

        def to_base(amount):
            return company_currency.round(amount / conv_rate)

        items = [it[2] for it in donation_vals.get('donation_item_ids', [])] + \
                [it[2] for it in donation_vals.get('qurbani_order_line_ids', [])]
        all_total = 0.0
        mapped_total = 0.0
        mapped_base = 0.0
        unbooked = False
        for item in items:
            item_total = float(item.get('total') or 0.0)
            if is_foreign:
                item_total = currency_rec.round(item_total)
            all_total += item_total
            label = ' / '.join(filter(None, (item.get('donation_type'), item.get('item'), item.get('type'))))
            config = self._resolve_product(all_data, item.get('donation_type', ''), item.get('item', ''),
                                           item.get('type', ''))
            if not config:
                notes.append(_('"%s" is not mapped to a product on the API gateway configuration.') % label)
                unbooked = True
                continue
            if not config['account_id']:
                notes.append(_('The product of "%s" has no Income Account.') % label)
                unbooked = True
                continue
            if not item_total:
                continue
            base = to_base(item_total)
            c = credit_accumulator[(config['account_id'], currency_rec.id)]
            c['credit_base'] += base
            if is_foreign:
                c['amount_currency'] -= item_total
            mapped_total += item_total
            mapped_base += base

        if not items:
            notes.append(_('The donation has no items.'))
        if not mapped_total:
            return done('not_in_entry' if unbooked or not items else 'in_entry')

        # Bank charges of the booked part of the donation.
        charges = float(donation_vals.get('bank_charges') or 0.0)
        if charges and all_total:
            charges = charges * mapped_total / all_total
        if is_foreign:
            charges = currency_rec.round(charges)
        charges_base = to_base(charges) if charges else 0.0
        if charges and not all_data.get('bank_charges_account_id'):
            notes.append(_('Bank charges %(amount)s %(currency)s are included in the gateway debit: set the '
                           'Bank Charges Account on the API gateway configuration.') % {
                'amount': charges, 'currency': currency_rec.name})
            charges = charges_base = 0.0
        if charges:
            d = debit_accumulator[(all_data['bank_charges_account_id'], currency_rec.id)]
            d['debit_base'] += charges_base
            if is_foreign:
                d['amount_currency'] += charges

        d = debit_accumulator[(debit_account_id, currency_rec.id)]
        d['debit_base'] += mapped_base - charges_base
        if is_foreign:
            d['amount_currency'] += mapped_total - charges

        return done('partial' if unbooked else 'in_entry')

    # ---------------------- Product mapping ----------------------
    @staticmethod
    def _item_names(it):
        """(donation type, item name, type name) of a raw API item."""
        def en_name(value):
            if isinstance(value, dict) and 'en' in value:
                return (value.get('en') or {}).get('name', '') or ''
            return ''
        return it.get('donationType', '') or '', en_name(it.get('item', {})), en_name(it.get('type', {}))

    @staticmethod
    def _resolve_product(all_data, donation_type, item, type_name):
        """Gateway mapping of an item: by "<donation type><item><type>" (journal
        entry key) or else by the item name (stock key until 17.0.1.2.0)."""
        lines = all_data['gateway_product_lines']
        for key in (f"{donation_type}{item}{type_name}", item):
            config = lines.get((key or '').strip().lower())
            if config:
                return config
        return None

    # ---------------------- Optimized Helper Methods ----------------------
    def _date_to_iso_z(self, date_val, t):
        dt = datetime.combine(date_val, t).replace(tzinfo=timezone.utc)
        return dt.isoformat(timespec='milliseconds').replace('+00:00', 'Z')

    def _parse_iso_to_dt_fast(self, iso_str, history):
        """Fast ISO datetime parsing"""
        if not iso_str:
            self.create_fetch_log(history.id, f"Missing datetime string: {iso_str}")

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
                        self.create_fetch_log(history.id, f"Failed to parse datetime '{iso_str}' with format '{fmt}'")

                        continue
                # Fallback to naive parsing
                return datetime.strptime(iso_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
        except Exception:
            self.create_fetch_log(history.id, f"Failed to parse datetime: {iso_str}")

            _logger.debug('Failed to parse datetime: %s', iso_str)
            return None

    # ---------------------- Journal Entry Creation ----------------------
    def _create_grouped_journal_move(self, journal, debit_accumulator, credit_accumulator, company_currency, history):
        self.create_fetch_log(history.id, f"Start _create_grouped_journal_move", 'Journal Entry Creation', 'Starting to create grouped journal entry with accumulated lines')

        """Create journal entry safely (currency constraint compliant)"""

        lines = []
        company_currency_id = company_currency.id

        # -----------------------------
        # Debit lines
        # -----------------------------
        for (account_id, currency_id), vals in debit_accumulator.items():
            debit_amount = company_currency.round(vals['debit_base'])
            if not debit_amount:
                self.create_fetch_log(history.id, f"Skipping debit line for account {account_id} and currency {currency_id} due to zero amount after rounding", 'Skipped', f"Debit line for account {account_id} and currency {currency_id} is skipped because the amount is zero after rounding")

                continue

            # Company currency line
            if currency_id == company_currency_id:
                lines.append((0, 0, {
                    'account_id': account_id,
                    'debit': debit_amount,
                    'credit': 0.0,
                    'name': 'Donation Import - Debit',
                }))
            # Foreign currency line
            else:
                lines.append((0, 0, {
                    'account_id': account_id,
                    'debit': debit_amount,
                    'credit': 0.0,
                    'currency_id': currency_id,
                    'amount_currency': self.env['res.currency'].browse(currency_id).round(vals['amount_currency']),
                    'name': 'Donation Import - Debit',
                }))

        # -----------------------------
        # Credit lines
        # -----------------------------
        for (account_id, currency_id), vals in credit_accumulator.items():
            credit_amount = company_currency.round(vals['credit_base'])
            if not credit_amount:
                continue

            # Company currency line
            if currency_id == company_currency_id:
                lines.append((0, 0, {
                    'account_id': account_id,
                    'debit': 0.0,
                    'credit': credit_amount,
                    'name': 'Donation Import - Credit',
                }))
            # Foreign currency line
            else:
                lines.append((0, 0, {
                    'account_id': account_id,
                    'debit': 0.0,
                    'credit': credit_amount,
                    'currency_id': currency_id,
                    'amount_currency': self.env['res.currency'].browse(currency_id).round(vals['amount_currency']),  # already negative
                    'name': 'Donation Import - Credit',
                }))

        if not lines:
            self.create_fetch_log(history.id, "No journal lines to create.", 'Error', "No journal lines to create.")

        # -----------------------------
        # Balance check before create
        # -----------------------------
        total_debit = sum(l[2]['debit'] for l in lines)
        total_credit = sum(l[2]['credit'] for l in lines)
        diff = company_currency.round(total_debit - total_credit)

        if not company_currency.is_zero(diff):
            diff_account = self._get_rounding_difference_account(journal, history)

            if diff > 0 and diff_account:
                # Need credit
                lines.append((0, 0, {
                    'account_id': diff_account.id,
                    'debit': 0.0,
                    'credit': abs(diff),
                    'name': 'Rounding Adjustment',
                }))
            elif diff_account:
                # Need debit
                lines.append((0, 0, {
                    'account_id': diff_account.id,
                    'debit': abs(diff),
                    'credit': 0.0,
                    'name': 'Rounding Adjustment',
                }))

        # -----------------------------
        # Create & Post Move
        # -----------------------------
        move = self.env['account.move'].sudo().create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': fields.Date.today(),
            'ref': f"Donation Import {fields.Date.today()}",
            'line_ids': lines,
        })

        self.create_fetch_log(history.id, f"End _create_grouped_journal_move", 'Journal Entry Creation', f"Completed creation of journal entry with ID {move.id} and {len(lines)} lines")
        # move.action_post()
        return move

    def _get_rounding_difference_account(self, journal, history):
        self.create_fetch_log(history.id, f"Start _get_rounding_difference_account", 'Journal Entry Creation', 'Attempting to find rounding difference account with proper fallbacks')

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
                self.create_fetch_log(history.id,  f"No suitable rounding difference account found. Please configure a default account on journal {journal.name} or set up a rounding difference account.", 'Error', f"No suitable rounding difference account found. Please configure a default account on journal {journal.name} or set up a rounding difference account.")
        
        self.create_fetch_log(history.id, f"End _get_rounding_difference_account", 'Journal Entry Creation', 'Completed search for rounding difference account')

        return diff_account