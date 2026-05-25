from odoo import models, fields, _
from odoo.exceptions import ValidationError
from datetime import datetime, time, timezone
from urllib.parse import urlparse
import requests
import logging
from collections import defaultdict
from pprint import pformat

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
    # LOG HELPER  — buffers logs and flushes in one ORM call
    # =========================================================
    # Each wizard call carries a small in-memory buffer.
    # Call _flush_logs(history_id) at checkpoints (end of page,
    # end of method, etc.) to write them all at once.

    def _buf_log(self, message, status, reason=''):
        """Append to the in-memory log buffer (no DB hit)."""
        if not hasattr(self, '_log_buffer'):
            self._log_buffer = []
        self._log_buffer.append({
            'name': message,
            'status': status,
            'reason': reason,
        })

    def _flush_logs(self, history_id):
        """Write all buffered logs in a single ORM create call."""
        if not getattr(self, '_log_buffer', None):
            return
        for entry in self._log_buffer:
            entry['fetch_history_id'] = history_id
        self.env['fetch.log'].create(self._log_buffer)
        self._log_buffer = []

    # Kept for backward-compat; now just buffers unless flush=True
    def create_fetch_log(self, history_id, message, status='', reason='', flush=False):
        self._buf_log(message, status, reason)
        if flush:
            self._flush_logs(history_id)

    # =========================================================
    # ENTRY POINT
    # =========================================================
    def action_fetch_donation(self):
        self.ensure_one()

        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError(_("Start Date must be earlier than or equal to End Date."))

        company = self.env.company
        if not (company.url and company.client_id and company.client_secret):
            raise ValidationError(_("Missing URL, Client ID, or Client Secret."))

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
        origin_host = urlparse(base_url).hostname or ''

        auth_url  = f"{company.url.rstrip('/')}/api/odoo/auth"
        donate_url = f"{company.url.rstrip('/')}/api/odoo/donationInfo"

        # ---------------------------------------------------------
        # FIX 1: Resume pagination from an existing fetch_history
        # for the same date range instead of always creating a new
        # one and resetting page to 1.
        # ---------------------------------------------------------
        PER_PAGE = 100   # FIX 2: 100 records per page

        existing_history = self.env['fetch.history'].search([
            ('start_date', '=', self.start_date),
            ('end_date',   '=', self.end_date),
            ('state',      '!=', 'done'),          # not yet completed
        ], order='id desc', limit=1)

        if existing_history:
            history = existing_history
            page = history.page or 1
            self._buf_log(
                f"Resuming existing fetch history ID={history.id} from page {page}",
                'Resumed', 'Found existing incomplete history'
            )
        else:
            history = self.env['fetch.history'].create({
                'start_date': self.start_date,
                'end_date':   self.end_date,
                'page':       1,
                'per_page':   PER_PAGE,
            })
            page = 1
            self._buf_log("Initiating donation fetch.", 'Initiated', 'Started')

        self._flush_logs(history.id)

        # =========================================================
        # PAGINATION LOOP
        # =========================================================
        donations_info = []

        while True:
            payload = {
                "status":  "success",
                "page":    page,
                "perPage": PER_PAGE,
            }
            if self.start_date:
                payload["startDate"] = self._date_to_iso_z(self.start_date, time.min)
            if self.end_date:
                payload["endDate"]   = self._date_to_iso_z(self.end_date, time(23, 59, 59))

            self._buf_log(f"Fetching page {page}", "Pagination", str(payload))
            self._flush_logs(history.id)   # flush before network call

            page_data = self._fetch_donations_from_api(
                auth_url, donate_url, company,
                base_url, origin_host, history,
                override_payload=payload
            )

            if not page_data:
                break

            donations_info.extend(page_data)

            # Persist the next page number so a resume picks up correctly
            history.write({'page': page + 1})
            page += 1

            if len(page_data) < PER_PAGE:
                break   # last page

        if not donations_info:
            self._buf_log("No donations found", 'No Data', 'Empty response')
            self._flush_logs(history.id)
            return True

        # =========================================================
        # ORIGINAL PROCESSING LOGIC (unchanged in structure)
        # =========================================================
        total_records   = len(donations_info)
        qurbani_records = [r for r in donations_info if r.get('qurbani') is True]
        normal_records  = [r for r in donations_info if r.get('qurbani') is not True]

        self._buf_log(
            "Donation Summary", "Summary",
            f"Total={total_records}, Qurbani={len(qurbani_records)}, Normal={len(normal_records)}"
        )
        self._flush_logs(history.id)

        journal          = self.env['account.journal'].search([('name', 'ilike', 'Bank')], limit=1)
        gateway_config   = self.env['gateway.config'].search([('name', '=', 'Web API')], limit=1)
        company_currency = company.currency_id

        all_data = self._prefetch_all_data(donations_info, gateway_config, company_currency, history)

        result = self._process_donations_bulk(
            donations_info, journal, gateway_config,
            company_currency, all_data, history
        )

        if result.get('new_donations') and journal and result.get('accumulators'):
            move = self._create_grouped_journal_move(
                journal,
                result['accumulators']['debit'],
                result['accumulators']['credit'],
                company_currency, history
            )
            history.write({
                'journal_entry_id': move.id,
                'picking_id': result.get('picking_id') or False,
                'state': 'done',    # mark completed so next run starts fresh
            })
            self.env['api.donation'].browse(result['new_donations']).write({
                'fetch_history_id': history.id
            })

        self._buf_log("Completed successfully", 'Completed', 'Done')
        self._flush_logs(history.id)
        return True

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
                    session, auth_url,
                    company.client_id, company.client_secret
                )
                session.headers.update({'authorization': f'bearer {token}'})

                if override_payload:
                    payload = override_payload
                else:
                    payload = {"status": "success"}
                    if self.start_date:
                        payload['startDate'] = self._date_to_iso_z(self.start_date, time.min)
                    if self.end_date:
                        payload['endDate']   = self._date_to_iso_z(self.end_date, time(23, 59, 59))

                resp = session.post(donate_url, json=payload, timeout=60)
                resp.raise_for_status()
                data = resp.json()

                if not isinstance(data, dict) or 'donationsInfo' not in data:
                    raise ValidationError(_("Invalid Donations Info"))

                return data.get('donationsInfo') or []

        except Exception as e:
            raise ValidationError(_('API Error: %s') % str(e))

    # =========================================================
    # AUTHENTICATION
    # =========================================================
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

    # =========================================================
    # BULK DATA PRE-FETCHING
    # =========================================================
    def _prefetch_all_data(self, donations_info, gateway_config, company_currency, history):
        self._buf_log("Start _prefetch_all_data", 'Prefetching',
                      'Starting to prefetch all required data for processing')

        unique_currencies    = set()
        unique_import_ids    = set()
        unique_country_codes = set()
        unique_mobiles       = set()

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
                if mobile:
                    unique_mobiles.add(mobile)

        self._buf_log(
            f"Unique Currencies: {unique_currencies}, Country Codes: {unique_country_codes}, "
            f"Mobiles: {unique_mobiles}, Import IDs: {unique_import_ids}",
            'Prefetching', 'Extracted unique values'
        )

        currencies       = self.env['res.currency'].search([('name', 'in', list(unique_currencies))])
        currency_by_name = {c.name.lower(): c for c in currencies}

        conversion_rates = {}
        for currency in currencies:
            if currency.rate_ids:
                latest_rate = currency.rate_ids.sorted('name', reverse=True)[0]
                conversion_rates[currency.name.lower()] = float(latest_rate.company_rate or 1.0)
            else:
                conversion_rates[currency.name.lower()] = 1.0

        self._buf_log(f"Conversion Rates: {conversion_rates}", 'Prefetching', 'Fetched conversion rates')

        countries        = self.env['res.country'].search([('code', 'in', list(unique_country_codes))])
        country_by_code  = {c.code: c.id for c in countries}

        existing_import_ids = set()
        if unique_import_ids:
            existing_records    = self.env['api.donation'].search_read(
                [('import_id', 'in', list(unique_import_ids))], ['import_id']
            )
            existing_import_ids = {r['import_id'] for r in existing_records}

        self._buf_log(f"Existing Import IDs: {existing_import_ids}", 'Prefetching',
                      'Fetched existing import IDs')

        partner_cache = {}
        if unique_mobiles:
            donor_category    = self.env.ref('bn_profile_management.donor_partner_category',
                                             raise_if_not_found=False)
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

        self._buf_log(f"Partner Cache: {partner_cache}", 'Prefetching', 'Fetched partner cache')

        gateway_currency_lines = {}
        if gateway_config:
            for line in gateway_config.gateway_config_currency_ids:
                currency_name = (line.currency_id.name or '').strip().lower()
                if currency_name:
                    gateway_currency_lines[currency_name] = line.account_id.id

        self._buf_log(f"Gateway Currency Lines: {gateway_currency_lines}", 'Prefetching',
                      'Fetched gateway currency lines')

        gateway_product_lines = {}
        if gateway_config:
            for line in gateway_config.gateway_config_line_ids:
                product_name = (line.name or '').strip().lower()
                if product_name:
                    gateway_product_lines[product_name] = {
                        'account_id': line.product_id.property_account_income_id.id,
                        'product_id': line.product_id.id,
                    }

        donor_category      = self.env.ref('bn_profile_management.donor_partner_category',
                                           raise_if_not_found=False)
        individual_category = self.env.ref('bn_profile_management.individual_partner_category',
                                           raise_if_not_found=False)
        default_partner     = self.env['res.partner'].search(
            [('primary_registration_id', '=', '2025-9999998-9')], limit=1
        )
        default_partner_id  = default_partner.id if default_partner else False

        self._buf_log("End _prefetch_all_data", 'Prefetching', 'Completed prefetching')
        self._flush_logs(history.id)   # flush after prefetch phase

        return {
            'currency_by_name':      currency_by_name,
            'conversion_rates':      conversion_rates,
            'country_by_code':       country_by_code,
            'existing_import_ids':   existing_import_ids,
            'partner_cache':         partner_cache,
            'gateway_currency_lines': gateway_currency_lines,
            'gateway_product_lines': gateway_product_lines,
            'donor_category_ids': [
                donor_category.id    if donor_category    else False,
                individual_category.id if individual_category else False
            ],
            'default_partner_id': default_partner_id,
        }

    # =========================================================
    # BULK PROCESSING
    # =========================================================
    def _process_donations_bulk(self, donations_info, journal, gateway_config,
                                company_currency, all_data, history):
        self._buf_log("Start _process_donations_bulk", "Processing",
                      "Starting bulk donation processing")

        new_donation_ids    = []
        debit_accumulator   = defaultdict(lambda: {'debit_base': 0.0, 'amount_currency': 0.0})
        credit_accumulator  = defaultdict(lambda: {'credit_base': 0.0, 'amount_currency': 0.0})
        StockPicking        = self.env['stock.picking']
        StockMove           = self.env['stock.move']
        stock_accumulator   = defaultdict(float)

        total_records = skipped_records = processed_records = 0
        total_partner_requests = duplicate_partner_requests = 0
        already_existing_partners = actually_created_partners = 0

        donations_to_create = []
        partner_to_create   = []
        partner_mapping     = {}

        for info_idx, info in enumerate(donations_info):
            total_records += 1
            import_id = info.get('_id')

            if not import_id or import_id in all_data['existing_import_ids']:
                skipped_records += 1
                self._buf_log(
                    f"Skipping donation import_id={import_id}",
                    'Skipped',
                    f"Already exists or missing import_id"
                )
                continue

            processed_records += 1
            donation_vals = self._prepare_donation_vals_fast(
                info, all_data, info_idx,
                partner_to_create, partner_mapping, history
            )
            if donation_vals:
                donations_to_create.append(donation_vals)
                if gateway_config and journal:
                    self._accumulate_donation_lines_fast(
                        donation_vals, all_data, company_currency,
                        debit_accumulator, credit_accumulator, history
                    )

            # Stock accumulation
            for it in (info.get('items') or []):
                item_data = it.get('item', {})
                item_name = ''
                if isinstance(item_data, dict) and 'en' in item_data:
                    item_name = item_data['en'].get('name', '')
                normalized = (item_name or '').strip().lower()
                product_line = gateway_config.gateway_config_line_ids.filtered(
                    lambda l: (l.name or '').strip().lower() == normalized
                )
                product = product_line.product_id if product_line else False
                if product and product.detailed_type == 'product':
                    stock_accumulator[product.id] += float(it.get('qty') or 1.0)

        # Flush per-donation log buffer before expensive partner ops
        self._flush_logs(history.id)

        # ---------------------------------------------------------
        # PARTNER DEDUPLICATION
        # ---------------------------------------------------------
        self._buf_log(f"Partner requests before dedup: {len(partner_to_create)}", 'Debug',
                      'Total partner requests collected')
        total_partner_requests = len(partner_to_create)

        seen             = set()
        unique_partners  = []
        for vals in partner_to_create:
            key = (vals.get('mobile'), vals.get('country_code_id'))
            if key not in seen:
                seen.add(key)
                unique_partners.append(vals)
            else:
                duplicate_partner_requests += 1

        partner_to_create[:] = unique_partners
        self._buf_log(
            f"Duplicate partner requests removed: {duplicate_partner_requests}",
            'Debug', 'After dedup'
        )

        # ---------------------------------------------------------
        # CHECK EXISTING PARTNERS  (single bulk search, not per-partner)
        # ---------------------------------------------------------
        existing_emails   = {v['email']  for v in partner_to_create if v.get('email')}
        existing_mobiles  = {v['mobile'] for v in partner_to_create if v.get('mobile')}

        if existing_emails or existing_mobiles:
            domain = []
            if existing_emails:
                domain += [('email', 'in', list(existing_emails))]
            if existing_mobiles:
                if domain:
                    domain = ['|'] + domain
                domain += [('mobile', 'in', list(existing_mobiles))]

            found_partners = self.env['res.partner'].search_read(
                domain, ['email', 'mobile']
            )
            existing_email_set  = {p['email']  for p in found_partners if p.get('email')}
            existing_mobile_set = {p['mobile'] for p in found_partners if p.get('mobile')}
        else:
            existing_email_set  = set()
            existing_mobile_set = set()

        partners_to_create_final = []
        for vals in partner_to_create:
            if (vals.get('email')  in existing_email_set or
                    vals.get('mobile') in existing_mobile_set):
                already_existing_partners += 1
                self._buf_log(
                    f"Partner already exists: mobile={vals.get('mobile')}",
                    'Debug', 'Existing partner found'
                )
                continue
            if not vals.get('name'):
                self._buf_log(
                    f"Skipping partner with missing name",
                    'Warning', f"Data: {vals}"
                )
                continue
            if not vals.get('mobile') and not vals.get('email'):
                self._buf_log(
                    f"Skipping partner {vals.get('name')} — no contact info",
                    'Warning', f"Data: {vals}"
                )
                continue
            partners_to_create_final.append(vals)

        self._buf_log(
            f"Partners existing={already_existing_partners}, to create={len(partners_to_create_final)}",
            'Debug', 'Partner check done'
        )
        self._flush_logs(history.id)

        # ---------------------------------------------------------
        # ACTUAL PARTNER CREATE
        # ---------------------------------------------------------
        created_partners = self.env['res.partner']
        if partners_to_create_final:
            try:
                self._buf_log(
                    f"Creating {len(partners_to_create_final)} partners",
                    'Processing', str(partners_to_create_final)
                )
                created_partners = self.env['res.partner'].create(partners_to_create_final)
                actually_created_partners = len(created_partners)
                self._buf_log(
                    f"Successfully created {actually_created_partners} partners",
                    'Success', f"IDs: {created_partners.ids}"
                )
                for idx, partner_vals in enumerate(partners_to_create_final):
                    partner_key = (partner_vals.get('mobile'), partner_vals.get('country_code_id'))
                    if idx < len(created_partners):
                        partner_mapping[partner_key] = created_partners[idx].id

                self._buf_log(
                    f"Partner mapping: {len(partner_mapping)} entries",
                    'Success', str(partner_mapping)
                )
                try:
                    created_partners.action_register()
                    self._buf_log(
                        f"Registered {actually_created_partners} partners",
                        'Success', ''
                    )
                except Exception as register_error:
                    self._buf_log(
                        f"Partner registration warning",
                        'Warning', str(register_error)
                    )
                    _logger.warning(f"Partner registration error: {register_error}")

            except Exception as create_error:
                actually_created_partners = 0
                self._buf_log(
                    "FAILED to create partners",
                    'Error',
                    f"Error: {create_error}\nData: {partners_to_create_final}"
                )
                self._flush_logs(history.id)
                _logger.exception(f"Partner creation failed: {create_error}")
                raise ValidationError(f"Failed to create partners: {create_error}")
        else:
            self._buf_log("No new partners to create", 'Info', '')

        self._flush_logs(history.id)

        # ---------------------------------------------------------
        # DEBUG SUMMARY
        # ---------------------------------------------------------
        debug_summary = (
            f"TOTAL={total_records} SKIPPED={skipped_records} PROCESSED={processed_records} | "
            f"PARTNER REQUESTS={total_partner_requests} DUPES={duplicate_partner_requests} "
            f"EXISTING={already_existing_partners} CREATED={actually_created_partners}"
        )
        _logger.warning(debug_summary)
        self._buf_log(debug_summary, 'Debug Summary', 'Final summary')

        # ---------------------------------------------------------
        # LINK DONATIONS → PARTNERS
        # ---------------------------------------------------------
        donations_with_partner = donations_without_partner = 0
        for donation_val in donations_to_create:
            if 'partner_key' in donation_val:
                partner_id = partner_mapping.get(donation_val['partner_key'])
                if partner_id:
                    donation_val['donor_id'] = partner_id
                    donations_with_partner += 1
                else:
                    self._buf_log(
                        f"Donation could not be linked to partner",
                        'Warning',
                        f"Key {donation_val['partner_key']} not in mapping"
                    )
                    donations_without_partner += 1
                del donation_val['partner_key']
            else:
                if donation_val.get('donor_id'):
                    donations_with_partner += 1
                else:
                    donations_without_partner += 1

        self._buf_log(
            f"Donation-Partner link: with={donations_with_partner} without={donations_without_partner}",
            'Success', f"Total to create: {len(donations_to_create)}"
        )

        # ---------------------------------------------------------
        # CREATE DONATIONS
        # ---------------------------------------------------------
        if donations_to_create:
            new_donations    = self.env['api.donation'].create(donations_to_create)
            new_donation_ids = new_donations.ids

        # ---------------------------------------------------------
        # STOCK PICKING
        # ---------------------------------------------------------
        picking = False
        if stock_accumulator:
            picking_type = self.picking_type_id
            if not picking_type:
                raise ValidationError(_("Stock Picking Type is missing."))

            picking = StockPicking.create({
                'picking_type_id':    picking_type.id,
                'location_id':        self.source_location_id.id,
                'location_dest_id':   self.destination_location_id.id,
                'origin':             f"API Donation {fields.Date.today()}",
            })
            for product_id, qty in stock_accumulator.items():
                product = self.env['product.product'].browse(product_id)
                StockMove.create({
                    'name':             product.display_name,
                    'product_id':       product.id,
                    'product_uom_qty':  qty,
                    'quantity':         qty,
                    'product_uom':      product.uom_id.id,
                    'picking_id':       picking.id,
                    'location_id':      self.source_location_id.id,
                    'location_dest_id': self.destination_location_id.id,
                })
            picking.action_confirm()
            picking.action_assign()
            picking.button_validate()

        self._buf_log("End _process_donations_bulk", 'Processing', 'Completed bulk processing')
        self._flush_logs(history.id)

        return {
            'new_donations': new_donation_ids,
            'accumulators': {
                'debit':  dict(debit_accumulator),
                'credit': dict(credit_accumulator),
            },
            'picking_id': picking.id if picking else False
        }

    # =========================================================
    # PREPARE DONATION VALS
    # =========================================================
    def _prepare_donation_vals_fast(self, info, all_data, info_idx,
                                    partner_to_create, partner_mapping, history):
        if info.get('status') != 'success':
            self._buf_log(
                f"Skipping non-success donation idx={info_idx}",
                'Skipped', f"status={info.get('status')}"
            )
            return None

        created_dt = self._parse_iso_to_dt_fast(info.get('createdAt'), history)
        updated_dt = self._parse_iso_to_dt_fast(info.get('updatedAt'), history)

        currency_name = info.get('currency', '') or ''
        conv_rate     = all_data['conversion_rates'].get(currency_name.lower(), 1.0)

        if currency_name.lower() and currency_name.lower() not in all_data['currency_by_name']:
            self._buf_log(
                f"Currency {currency_name} not found, using company currency",
                'Error', ''
            )
            currency_name = self.env.company.currency_id.name.lower()
            conv_rate     = 1.0

        total_amount = (float(info.get('total_amount', 0) or 0)
                        - float(info.get('bank_charges', 0) or 0))
        total_local  = total_amount / conv_rate

        donor       = info.get('donor_details') or {}
        donor_id    = None
        partner_key = None

        if donor.get('name', ''):
            mobile      = donor.get('phone', '')[-10:] if donor.get('phone') else ''
            country_code = donor.get('country', '')
            country_id  = all_data['country_by_code'].get(country_code)

            if mobile and country_id:
                for cached_key, cached_id in all_data['partner_cache'].items():
                    if cached_key[0] == mobile and cached_key[1] == country_id:
                        donor_id = cached_id
                        break

            if not donor_id:
                partner_vals = {
                    'name':            donor.get('name', ''),
                    'mobile':          mobile,
                    'email':           donor.get('email', ''),
                    'country_code_id': country_id,
                    'category_id':     [(6, 0, [cid for cid in all_data['donor_category_ids'] if cid])],
                }
                partner_to_create.append(partner_vals)
                partner_key = (mobile, country_id)
        else:
            donor_id = all_data['default_partner_id']

        items     = info.get('items') or []
        orm_items = []
        order_lines = []

        for it in items:
            types_name = ''
            item_name  = ''

            type_data = it.get('type', {})
            if isinstance(type_data, dict) and 'en' in type_data:
                types_name = type_data['en'].get('name', '')

            item_data = it.get('item', {})
            if isinstance(item_data, dict) and 'en' in item_data:
                item_name = item_data['en'].get('name', '')

            if info.get('qurbani') is not True:
                orm_items.append({
                    'donation_type': it.get('donationType', ''),
                    'total':         float(it.get('total', 0) or 0),
                    'price':         it.get('price', 0),
                    'price_id':      it.get('price_id', 0),
                    'qty':           it.get('qty', 0),
                    'type':          types_name,
                    'item':          item_name,
                    'donation_no':   it.get('donationNo', 0),
                    'is_priced_item': it.get('isPricedItem', False),
                })
            else:
                product     = False
                product_key = (
                    f"{info.get('donationType', '')}"
                    f"{item_name}"
                    f"{types_name}"
                ).strip().lower()

                config = all_data['gateway_product_lines'].get(product_key)
                if config:
                    product = self.env['product.product'].browse(config['product_id'])
                if not product:
                    self._buf_log(
                        f"Qurbani product not found idx={info_idx}",
                        'Error',
                        f"Key={product_key} Gateway lines={all_data['gateway_product_lines']}"
                    )

                quantity    = int(it.get('qty', 1) or 1)
                amount      = float(it.get('price', 0) or 0)
                day_name    = it.get('day', '')
                city_name   = it.get('qurbaniCity', '')
                branch_name = it.get('qurbaniBranch', '')
                qurbani_ff  = it.get('qurbaniFulfillment', '')

                share_names = it.get('share_names', [donor.get('name', '')])
                if not share_names:
                    share_names = [donor.get('name', '')]

                for idx in range(quantity):
                    share_name = share_names[idx % len(share_names)]
                    hissa_name = (
                        f"{idx + 1}. {share_name}" if quantity > 1 else share_name
                    )
                    line_vals = {
                        'product_id':          product.id if product else False,
                        'quantity':            1,
                        'amount':              amount,
                        'day':                 day_name    or False,
                        'city':                city_name   or False,
                        'hissa_name':          hissa_name,
                        'branch':              branch_name or False,
                        'qurbani_fullfilment': qurbani_ff  or False,
                    }
                    order_lines.append([0, 0, line_vals])

        donation_vals = {
            'import_id':                    info.get('_id', ''),
            'remarks':                      info.get('remarks', ''),
            'total_amount':                 total_amount,
            'total_amount_local':           total_local,
            'donor':                        info.get('donor', ''),
            'donation_type':                info.get('donation_type', ''),
            'donation_from':                info.get('donation_from', ''),
            'dn_number':                    info.get('DN_Number', ''),
            'subscription_interval':        info.get('subscriptionInterval', ''),
            'is_recurring':                 info.get('isRecurring', False),
            'response_code':                info.get('response_code', ''),
            'response_description':         info.get('response_description', ''),
            'currency':                     currency_name,
            'referer':                      info.get('referer', ''),
            'website':                      info.get('website', ''),
            'account_source':               info.get('account_source', ''),
            'conversion_rate':              conv_rate,
            'bank_charges':                 info.get('bank_charges', 0),
            'bank_charges_in_text':         info.get('bank_charges_in_text', ''),
            'blinq_notification_number':    info.get('blinq_notification_number', ''),
            'created_at':                   created_dt,
            'updated_at':                   updated_dt,
            'donation_id':                  info.get('donation_id', ''),
            'invoice_id':                   info.get('invoice_id', ''),
            'transaction_id':               info.get('transaction_id', ''),
            'name':                         donor.get('name', ''),
            'phone':                        donor.get('phone', ''),
            'email':                        donor.get('email', ''),
            'cnic':                         donor.get('cnic', ''),
            'country':                      donor.get('country', ''),
            'ip_address':                   donor.get('ipAddress', ''),
            'subscription_for_news':        donor.get('subscriptionForNews', False),
            'subscription_for_whatsapp':    donor.get('subscriptionForWhatsapp', False),
            'subscription_for_sms':         donor.get('subscriptionForSms', False),
            'qurbani_country':              donor.get('qurbaniCountry', ''),
            'qurbani_city':                 donor.get('qurbaniCity', ''),
            'qurbani_day':                  donor.get('qurbaniDay', ''),
            'donation_item_ids':            [(0, 0, it) for it in orm_items],
            'qurbani_order_line_ids':       order_lines,
            'fetch_history_id':             history.id,
            'qurbani':                      info.get('qurbani') is True,
        }

        if donor_id:
            donation_vals['donor_id'] = donor_id
        elif partner_key is not None:
            donation_vals['partner_key'] = partner_key
        else:
            donation_vals['donor_id'] = all_data['default_partner_id']

        return donation_vals

    # =========================================================
    # ACCUMULATE JOURNAL LINES
    # =========================================================
    def _accumulate_donation_lines_fast(self, donation_vals, all_data, company_currency,
                                        debit_accumulator, credit_accumulator, history):
        currency_name = donation_vals.get('currency', '')
        currency_rec  = all_data['currency_by_name'].get(currency_name.lower())
        if not currency_rec:
            self._buf_log(
                f"Currency {currency_name} not found, skipping journal accumulation",
                'Error', ''
            )
            return

        debit_account_id = all_data['gateway_currency_lines'].get(currency_name.lower())
        if not debit_account_id:
            self._buf_log(
                f"Debit account not found for currency {currency_name}",
                'Error', ''
            )
            return

        is_foreign = currency_rec != company_currency

        for it in donation_vals.get('donation_item_ids', []):
            item         = it[2]
            product_name = (
                f"{item.get('donation_type', '')}"
                f"{item.get('item', '')}"
                f"{item.get('type', '')}"
            ).strip().lower()

            config = all_data['gateway_product_lines'].get(product_name)
            if not config:
                self._buf_log(
                    f"Product config not found: {product_name}",
                    'Error', ''
                )
                continue

            credit_account_id = config['account_id']
            if not credit_account_id:
                continue

            item_total      = float(item.get('total', 0))
            conv_rate       = float(donation_vals.get('conversion_rate', 1.0))

            if is_foreign:
                item_total = currency_rec.round(item_total)

            item_total_base = company_currency.round(item_total / conv_rate)
            currency_id     = currency_rec.id

            debit_key = (debit_account_id, currency_id)
            d = debit_accumulator[debit_key]
            d['debit_base'] += item_total_base
            if is_foreign:
                d['amount_currency'] += item_total

            credit_key = (credit_account_id, currency_id)
            c = credit_accumulator[credit_key]
            c['credit_base'] += item_total_base
            if is_foreign:
                c['amount_currency'] -= item_total

    # =========================================================
    # HELPER METHODS
    # =========================================================
    def _date_to_iso_z(self, date_val, t):
        dt = datetime.combine(date_val, t).replace(tzinfo=timezone.utc)
        return dt.isoformat(timespec='milliseconds').replace('+00:00', 'Z')

    def _parse_iso_to_dt_fast(self, iso_str, history):
        if not iso_str:
            return None
        try:
            if 'T' in iso_str:
                if 'Z' in iso_str:
                    return datetime.fromisoformat(
                        iso_str.replace('Z', '+00:00')
                    ).replace(tzinfo=None)
                elif '+' in iso_str or '-' in iso_str[10:]:
                    return datetime.fromisoformat(iso_str).replace(tzinfo=None)
                else:
                    return datetime.fromisoformat(iso_str)
            else:
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S',
                            '%Y-%m-%d', '%Y/%m/%d']:
                    try:
                        return datetime.strptime(iso_str, fmt)
                    except ValueError:
                        continue
                return datetime.strptime(iso_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
        except Exception:
            _logger.debug('Failed to parse datetime: %s', iso_str)
            return None

    # =========================================================
    # JOURNAL ENTRY CREATION
    # =========================================================
    def _create_grouped_journal_move(self, journal, debit_accumulator,
                                     credit_accumulator, company_currency, history):
        self._buf_log("Start _create_grouped_journal_move", 'Journal Entry Creation', '')

        lines              = []
        company_currency_id = company_currency.id

        for (account_id, currency_id), vals in debit_accumulator.items():
            debit_amount = company_currency.round(vals['debit_base'])
            if not debit_amount:
                continue
            line = {'account_id': account_id, 'debit': debit_amount,
                    'credit': 0.0, 'name': 'Donation Import - Debit'}
            if currency_id != company_currency_id:
                line['currency_id']      = currency_id
                line['amount_currency']  = company_currency.round(vals['amount_currency'])
            lines.append((0, 0, line))

        for (account_id, currency_id), vals in credit_accumulator.items():
            credit_amount = company_currency.round(vals['credit_base'])
            if not credit_amount:
                continue
            line = {'account_id': account_id, 'debit': 0.0,
                    'credit': credit_amount, 'name': 'Donation Import - Credit'}
            if currency_id != company_currency_id:
                line['currency_id']      = currency_id
                line['amount_currency']  = company_currency.round(vals['amount_currency'])
            lines.append((0, 0, line))

        if not lines:
            self._buf_log("No journal lines to create.", 'Error', '')
            self._flush_logs(history.id)
            return self.env['account.move']

        total_debit  = sum(l[2]['debit']  for l in lines)
        total_credit = sum(l[2]['credit'] for l in lines)
        diff         = company_currency.round(total_debit - total_credit)

        if not company_currency.is_zero(diff):
            diff_account = self._get_rounding_difference_account(journal, history)
            if diff_account:
                if diff > 0:
                    lines.append((0, 0, {'account_id': diff_account.id,
                                         'debit': 0.0, 'credit': abs(diff),
                                         'name': 'Rounding Adjustment'}))
                else:
                    lines.append((0, 0, {'account_id': diff_account.id,
                                         'debit': abs(diff), 'credit': 0.0,
                                         'name': 'Rounding Adjustment'}))

        move = self.env['account.move'].sudo().create({
            'move_type':  'entry',
            'journal_id': journal.id,
            'date':       fields.Date.today(),
            'ref':        f"Donation Import {fields.Date.today()}",
            'line_ids':   lines,
        })

        self._buf_log(
            f"Journal entry created ID={move.id} lines={len(lines)}",
            'Journal Entry Creation', ''
        )
        self._flush_logs(history.id)
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
            if not diff_account:
                self._buf_log(
                    f"No rounding account found for journal {journal.name}",
                    'Error', ''
                )

        return diff_account