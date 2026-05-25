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
    end_date   = fields.Date('End Date')

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
        string="Source Location", store=True
    )
    destination_location_id = fields.Many2one(
        related='picking_type_id.default_location_dest_id',
        string="Destination Location", store=True
    )

    PER_PAGE = 100

    # =========================================================
    # LOG HELPERS  — buffer → single bulk INSERT per checkpoint
    # =========================================================
    # self.env is a plain Python object; object.__setattr__ bypasses
    # Odoo's field-only __setattr__ guard on the recordset itself.

    @property
    def _log_buffer(self):
        if not hasattr(self.env, '_fetch_log_buffer'):
            object.__setattr__(self.env, '_fetch_log_buffer', [])
        return self.env._fetch_log_buffer

    def _buf_log(self, message, status='', reason=''):
        self._log_buffer.append({'name': message, 'status': status, 'reason': reason})

    def _flush_logs(self, history_id):
        buf = self._log_buffer
        if not buf:
            return
        for e in buf:
            e['fetch_history_id'] = history_id
        self.env['fetch.log'].create(buf)
        buf.clear()

    def create_fetch_log(self, history_id, message, status='', reason='', flush=False):
        """Backward-compat wrapper — buffers unless flush=True."""
        self._buf_log(message, status, reason)
        if flush:
            self._flush_logs(history_id)

    # =========================================================
    # ENTRY POINT  — returns immediately; work runs in background
    # =========================================================
    def action_fetch_donation(self):
        """
        Validate inputs, create/resume a fetch.history, then enqueue
        a queue_job for the first (or next) page and return immediately.
        The browser never blocks.
        """
        self.ensure_one()

        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError(_("Start Date must be earlier than or equal to End Date."))

        company = self.env.company
        if not (company.url and company.client_id and company.client_secret):
            raise ValidationError(_("Missing URL, Client ID, or Client Secret."))

        # Resume an incomplete history for the same date range, or start fresh
        existing = self.env['fetch.history'].search([
            ('start_date', '=', self.start_date),
            ('end_date',   '=', self.end_date),
            ('state',      '!=', 'done'),
        ], order='id desc', limit=1)

        if existing:
            history    = existing
            start_page = history.page or 1
            self._buf_log(
                f"Resuming history ID={history.id} from page {start_page}",
                'Resumed', 'Found existing incomplete history'
            )
        else:
            history = self.env['fetch.history'].create({
                'start_date': self.start_date,
                'end_date':   self.end_date,
                'page':       1,
                'per_page':   self.PER_PAGE,
                'state':      'running',
            })
            start_page = 1
            self._buf_log("Donation fetch queued.", 'Initiated', 'Background job dispatched')

        self._flush_logs(history.id)

        # Enqueue page job — each job chains the next page itself
        self.env['fetch.history'].sudo().with_delay(
            description=f"Donation import – history {history.id} page {start_page}",
            max_retries=3,
            channel='root.donation_import',
        )._run_donation_page_job(
            history_id              = history.id,
            page                    = start_page,
            start_date              = str(self.start_date)              if self.start_date              else None,
            end_date                = str(self.end_date)                if self.end_date                else None,
            picking_type_id         = self.picking_type_id.id           if self.picking_type_id         else False,
            source_location_id      = self.source_location_id.id        if self.source_location_id      else False,
            destination_location_id = self.destination_location_id.id   if self.destination_location_id else False,
        )

        return {
            'type': 'ir.actions.client',
            'tag':  'display_notification',
            'params': {
                'title':   _('Import Started'),
                'message': _(
                    'Donation import is running in the background '
                    '(History ID: %s, starting page %s). '
                    'Refresh the Fetch History list to track progress.'
                ) % (history.id, start_page),
                'type':    'success',
                'sticky': False,
            },
        }

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
                    'Origin':          base_url,
                    'x-forwarded-for': origin_host,
                    'Content-Type':    'application/json',
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
            "ClientID":     client_id,
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
            f"Mobiles count: {len(unique_mobiles)}, Import IDs count: {len(unique_import_ids)}",
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

        countries       = self.env['res.country'].search([('code', 'in', list(unique_country_codes))])
        country_by_code = {c.code: c.id for c in countries}

        existing_import_ids = set()
        if unique_import_ids:
            existing_records    = self.env['api.donation'].search_read(
                [('import_id', 'in', list(unique_import_ids))], ['import_id']
            )
            existing_import_ids = {r['import_id'] for r in existing_records}

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
                    cc_id = partner.get('country_code_id')
                    cc_id = cc_id[0] if cc_id else False
                    partner_cache[(partner.get('mobile'), cc_id)] = partner['id']

        gateway_currency_lines = {}
        if gateway_config:
            for line in gateway_config.gateway_config_currency_ids:
                cn = (line.currency_id.name or '').strip().lower()
                if cn:
                    gateway_currency_lines[cn] = line.account_id.id

        gateway_product_lines = {}
        if gateway_config:
            for line in gateway_config.gateway_config_line_ids:
                pn = (line.name or '').strip().lower()
                if pn:
                    gateway_product_lines[pn] = {
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

        self._buf_log("End _prefetch_all_data", 'Prefetching', 'Completed prefetching')
        self._flush_logs(history.id)

        return {
            'currency_by_name':       currency_by_name,
            'conversion_rates':       conversion_rates,
            'country_by_code':        country_by_code,
            'existing_import_ids':    existing_import_ids,
            'partner_cache':          partner_cache,
            'gateway_currency_lines': gateway_currency_lines,
            'gateway_product_lines':  gateway_product_lines,
            'donor_category_ids': [
                donor_category.id      if donor_category      else False,
                individual_category.id if individual_category else False,
            ],
            'default_partner_id': default_partner.id if default_partner else False,
        }

    # =========================================================
    # BULK PROCESSING
    # =========================================================
    def _process_donations_bulk(self, donations_info, journal, gateway_config,
                                company_currency, all_data, history,
                                picking_type_id=False, source_location_id=False,
                                destination_location_id=False):
        self._buf_log("Start _process_donations_bulk", "Processing", "Starting bulk processing")

        new_donation_ids   = []
        debit_accumulator  = defaultdict(lambda: {'debit_base': 0.0, 'amount_currency': 0.0})
        credit_accumulator = defaultdict(lambda: {'credit_base': 0.0, 'amount_currency': 0.0})
        stock_accumulator  = defaultdict(float)

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
                    f"Skipping import_id={import_id}", 'Skipped', 'Already exists or missing'
                )
                continue

            processed_records += 1
            donation_vals = self._prepare_donation_vals_fast(
                info, all_data, info_idx, partner_to_create, partner_mapping, history
            )
            if donation_vals:
                donations_to_create.append(donation_vals)
                if gateway_config and journal:
                    self._accumulate_donation_lines_fast(
                        donation_vals, all_data, company_currency,
                        debit_accumulator, credit_accumulator, history
                    )

            for it in (info.get('items') or []):
                item_data = it.get('item', {})
                item_name = ''
                if isinstance(item_data, dict) and 'en' in item_data:
                    item_name = item_data['en'].get('name', '')
                normalized   = (item_name or '').strip().lower()
                product_line = gateway_config.gateway_config_line_ids.filtered(
                    lambda l: (l.name or '').strip().lower() == normalized
                )
                product = product_line.product_id if product_line else False
                if product and product.detailed_type == 'product':
                    stock_accumulator[product.id] += float(it.get('qty') or 1.0)

        self._flush_logs(history.id)

        # ---- Partner deduplication ----
        total_partner_requests = len(partner_to_create)
        seen, unique_partners = set(), []
        for vals in partner_to_create:
            key = (vals.get('mobile'), vals.get('country_code_id'))
            if key not in seen:
                seen.add(key)
                unique_partners.append(vals)
            else:
                duplicate_partner_requests += 1
        partner_to_create[:] = unique_partners

        # ---- Bulk check existing partners ----
        existing_emails  = {v['email']  for v in partner_to_create if v.get('email')}
        existing_mobiles = {v['mobile'] for v in partner_to_create if v.get('mobile')}
        existing_email_set = existing_mobile_set = set()

        if existing_emails or existing_mobiles:
            domain = []
            if existing_emails:
                domain += [('email', 'in', list(existing_emails))]
            if existing_mobiles:
                if domain:
                    domain = ['|'] + domain
                domain += [('mobile', 'in', list(existing_mobiles))]
            found = self.env['res.partner'].search_read(domain, ['email', 'mobile'])
            existing_email_set  = {p['email']  for p in found if p.get('email')}
            existing_mobile_set = {p['mobile'] for p in found if p.get('mobile')}

        partners_to_create_final = []
        for vals in partner_to_create:
            if (vals.get('email')  in existing_email_set or
                    vals.get('mobile') in existing_mobile_set):
                already_existing_partners += 1
                continue
            if not vals.get('name'):
                self._buf_log(f"Skipping partner — missing name", 'Warning', str(vals))
                continue
            if not vals.get('mobile') and not vals.get('email'):
                self._buf_log(f"Skipping partner — no contact info", 'Warning', str(vals))
                continue
            partners_to_create_final.append(vals)

        self._buf_log(
            f"Partners existing={already_existing_partners} to_create={len(partners_to_create_final)}",
            'Debug', ''
        )
        self._flush_logs(history.id)

        # ---- Create partners ----
        created_partners = self.env['res.partner']
        if partners_to_create_final:
            try:
                created_partners = self.env['res.partner'].create(partners_to_create_final)
                actually_created_partners = len(created_partners)
                self._buf_log(
                    f"Created {actually_created_partners} partners",
                    'Success', f"IDs: {created_partners.ids}"
                )
                for idx, pv in enumerate(partners_to_create_final):
                    if idx < len(created_partners):
                        partner_mapping[(pv.get('mobile'), pv.get('country_code_id'))] = \
                            created_partners[idx].id
                try:
                    created_partners.action_register()
                except Exception as reg_err:
                    self._buf_log("Partner registration warning", 'Warning', str(reg_err))
                    _logger.warning(f"Partner registration error: {reg_err}")
            except Exception as create_err:
                self._buf_log("FAILED to create partners", 'Error',
                              f"{create_err}\n{partners_to_create_final}")
                self._flush_logs(history.id)
                _logger.exception(f"Partner creation failed: {create_err}")
                raise ValidationError(f"Failed to create partners: {create_err}")
        else:
            self._buf_log("No new partners to create", 'Info', '')

        self._flush_logs(history.id)

        debug_summary = (
            f"TOTAL={total_records} SKIPPED={skipped_records} PROCESSED={processed_records} | "
            f"PARTNER_REQ={total_partner_requests} DUPES={duplicate_partner_requests} "
            f"EXISTING={already_existing_partners} CREATED={actually_created_partners}"
        )
        _logger.warning(debug_summary)
        self._buf_log(debug_summary, 'Debug Summary', '')

        # ---- Link donations to partners ----
        for donation_val in donations_to_create:
            if 'partner_key' in donation_val:
                pid = partner_mapping.get(donation_val['partner_key'])
                if pid:
                    donation_val['donor_id'] = pid
                else:
                    self._buf_log(
                        "Donation could not be linked to partner", 'Warning',
                        f"Key {donation_val['partner_key']} not in mapping"
                    )
                del donation_val['partner_key']

        # ---- Create donations ----
        if donations_to_create:
            new_donations    = self.env['api.donation'].create(donations_to_create)
            new_donation_ids = new_donations.ids

        # ---- Stock picking ----
        picking = False
        if stock_accumulator:
            pt = self.env['stock.picking.type'].browse(picking_type_id) if picking_type_id \
                else self.picking_type_id
            if not pt:
                raise ValidationError(_("Stock Picking Type is missing."))

            src  = source_location_id      or (self.source_location_id.id      if self.source_location_id      else False)
            dest = destination_location_id or (self.destination_location_id.id if self.destination_location_id else False)

            picking = self.env['stock.picking'].create({
                'picking_type_id':  pt.id,
                'location_id':      src,
                'location_dest_id': dest,
                'origin':           f"API Donation {fields.Date.today()}",
            })
            for product_id, qty in stock_accumulator.items():
                product = self.env['product.product'].browse(product_id)
                self.env['stock.move'].create({
                    'name':             product.display_name,
                    'product_id':       product.id,
                    'product_uom_qty':  qty,
                    'quantity':         qty,
                    'product_uom':      product.uom_id.id,
                    'picking_id':       picking.id,
                    'location_id':      src,
                    'location_dest_id': dest,
                })
            picking.action_confirm()
            picking.action_assign()
            picking.button_validate()

        self._buf_log("End _process_donations_bulk", 'Processing', 'Completed')
        self._flush_logs(history.id)

        return {
            'new_donations': new_donation_ids,
            'accumulators': {
                'debit':  dict(debit_accumulator),
                'credit': dict(credit_accumulator),
            },
            'picking_id': picking.id if picking else False,
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
                f"Currency {currency_name} not found, using company currency", 'Error', ''
            )
            currency_name = self.env.company.currency_id.name.lower()
            conv_rate     = 1.0

        total_amount = (float(info.get('total_amount', 0) or 0)
                        - float(info.get('bank_charges', 0) or 0))
        total_local  = total_amount / conv_rate if conv_rate else total_amount

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
                partner_to_create.append({
                    'name':            donor.get('name', ''),
                    'mobile':          mobile,
                    'email':           donor.get('email', ''),
                    'country_code_id': country_id,
                    'category_id':     [(6, 0, [cid for cid in all_data['donor_category_ids'] if cid])],
                })
                partner_key = (mobile, country_id)
        else:
            donor_id = all_data['default_partner_id']

        items = info.get('items') or []
        orm_items   = []
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
                    'donation_type':  it.get('donationType', ''),
                    'total':          float(it.get('total', 0) or 0),
                    'price':          it.get('price', 0),
                    'price_id':       it.get('price_id', 0),
                    'qty':            it.get('qty', 0),
                    'type':           types_name,
                    'item':           item_name,
                    'donation_no':    it.get('donationNo', 0),
                    'is_priced_item': it.get('isPricedItem', False),
                })
            else:
                product_key = (
                    f"{info.get('donationType', '')}{item_name}{types_name}"
                ).strip().lower()
                config  = all_data['gateway_product_lines'].get(product_key)
                product = self.env['product.product'].browse(config['product_id']) if config else False

                if not product:
                    self._buf_log(
                        f"Qurbani product not found idx={info_idx}",
                        'Error', f"Key={product_key}"
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
                    hissa_name = f"{idx + 1}. {share_name}" if quantity > 1 else share_name
                    order_lines.append([0, 0, {
                        'product_id':          product.id if product else False,
                        'quantity':            1,
                        'amount':              amount,
                        'day':                 day_name    or False,
                        'city':                city_name   or False,
                        'hissa_name':          hissa_name,
                        'branch':              branch_name or False,
                        'qurbani_fullfilment': qurbani_ff  or False,
                    }])

        donation_vals = {
            'import_id':                 info.get('_id', ''),
            'remarks':                   info.get('remarks', ''),
            'total_amount':              total_amount,
            'total_amount_local':        total_local,
            'donor':                     info.get('donor', ''),
            'donation_type':             info.get('donation_type', ''),
            'donation_from':             info.get('donation_from', ''),
            'dn_number':                 info.get('DN_Number', ''),
            'subscription_interval':     info.get('subscriptionInterval', ''),
            'is_recurring':              info.get('isRecurring', False),
            'response_code':             info.get('response_code', ''),
            'response_description':      info.get('response_description', ''),
            'currency':                  currency_name,
            'referer':                   info.get('referer', ''),
            'website':                   info.get('website', ''),
            'account_source':            info.get('account_source', ''),
            'conversion_rate':           conv_rate,
            'bank_charges':              info.get('bank_charges', 0),
            'bank_charges_in_text':      info.get('bank_charges_in_text', ''),
            'blinq_notification_number': info.get('blinq_notification_number', ''),
            'created_at':                created_dt,
            'updated_at':                updated_dt,
            'donation_id':               info.get('donation_id', ''),
            'invoice_id':                info.get('invoice_id', ''),
            'transaction_id':            info.get('transaction_id', ''),
            'name':                      donor.get('name', ''),
            'phone':                     donor.get('phone', ''),
            'email':                     donor.get('email', ''),
            'cnic':                      donor.get('cnic', ''),
            'country':                   donor.get('country', ''),
            'ip_address':                donor.get('ipAddress', ''),
            'subscription_for_news':     donor.get('subscriptionForNews', False),
            'subscription_for_whatsapp': donor.get('subscriptionForWhatsapp', False),
            'subscription_for_sms':      donor.get('subscriptionForSms', False),
            'qurbani_country':           donor.get('qurbaniCountry', ''),
            'qurbani_city':              donor.get('qurbaniCity', ''),
            'qurbani_day':               donor.get('qurbaniDay', ''),
            'donation_item_ids':         [(0, 0, it) for it in orm_items],
            'qurbani_order_line_ids':    order_lines,
            'fetch_history_id':          history.id,
            'qurbani':                   info.get('qurbani') is True,
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
        currency_name    = donation_vals.get('currency', '')
        currency_rec     = all_data['currency_by_name'].get(currency_name.lower())
        debit_account_id = all_data['gateway_currency_lines'].get(currency_name.lower())

        if not currency_rec or not debit_account_id:
            self._buf_log(
                f"Missing currency or debit account for {currency_name}", 'Error', ''
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
                self._buf_log(f"Product config not found: {product_name}", 'Error', '')
                continue

            credit_account_id = config['account_id']
            if not credit_account_id:
                continue

            item_total = float(item.get('total', 0))
            conv_rate  = float(donation_vals.get('conversion_rate', 1.0))

            if is_foreign:
                item_total = currency_rec.round(item_total)
            item_total_base = company_currency.round(item_total / conv_rate if conv_rate else item_total)
            currency_id     = currency_rec.id

            d = debit_accumulator[(debit_account_id, currency_id)]
            d['debit_base'] += item_total_base
            if is_foreign:
                d['amount_currency'] += item_total

            c = credit_accumulator[(credit_account_id, currency_id)]
            c['credit_base'] += item_total_base
            if is_foreign:
                c['amount_currency'] -= item_total

    # =========================================================
    # HELPER METHODS
    # =========================================================
    def _date_to_iso_z(self, date_val, t):
        dt = datetime.combine(date_val, t).replace(tzinfo=timezone.utc)
        return dt.isoformat(timespec='milliseconds').replace('+00:00', 'Z')

    def _parse_iso_to_dt_fast(self, iso_str, history=None):
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

        lines               = []
        company_currency_id = company_currency.id

        for (account_id, currency_id), vals in debit_accumulator.items():
            debit_amount = company_currency.round(vals['debit_base'])
            if not debit_amount:
                continue
            line = {'account_id': account_id, 'debit': debit_amount,
                    'credit': 0.0, 'name': 'Donation Import - Debit'}
            if currency_id != company_currency_id:
                line['currency_id']     = currency_id
                line['amount_currency'] = company_currency.round(vals['amount_currency'])
            lines.append((0, 0, line))

        for (account_id, currency_id), vals in credit_accumulator.items():
            credit_amount = company_currency.round(vals['credit_base'])
            if not credit_amount:
                continue
            line = {'account_id': account_id, 'debit': 0.0,
                    'credit': credit_amount, 'name': 'Donation Import - Credit'}
            if currency_id != company_currency_id:
                line['currency_id']     = currency_id
                line['amount_currency'] = company_currency.round(vals['amount_currency'])
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
                lines.append((0, 0, {
                    'account_id': diff_account.id,
                    'debit':  0.0       if diff > 0 else abs(diff),
                    'credit': abs(diff) if diff > 0 else 0.0,
                    'name':   'Rounding Adjustment',
                }))

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
            acc = self.env['account.account'].search([
                ('code', 'like', f"{company.difference_account_prefix}%"),
                ('company_id', '=', company.id)
            ], limit=1)
            if acc:
                return acc
        acc = self.env['account.account'].search([
            ('account_type', 'in', ['expense', 'income']),
            ('name', 'ilike', 'rounding'),
            ('company_id', '=', company.id)
        ], limit=1)
        if not acc:
            acc = self.env['account.account'].search([
                ('account_type', '=', 'expense'),
                ('company_id', '=', company.id)
            ], limit=1)
        if not acc:
            self._buf_log(
                f"No rounding account found for journal {journal.name}", 'Error', ''
            )
        return acc


# =================================================================
# FETCH HISTORY MODEL EXTENSION
# Add this mixin/extension to your fetch.history model, OR paste
# the _run_donation_page_job method directly into that model.
# =================================================================
class FetchHistory(models.Model):
    """
    Extend fetch.history with the per-page background job method.

    Required new fields on fetch.history (add to your model):
        state    = fields.Selection([('running','Running'),('done','Done')], default='running')
        page     = fields.Integer(default=1)
        per_page = fields.Integer(default=100)
    """
    _inherit = 'fetch.history'

    def _run_donation_page_job(
        self, history_id, page,
        start_date=None, end_date=None,
        picking_type_id=False, source_location_id=False,
        destination_location_id=False,
    ):
        """
        Queued job: fetch + process ONE page of donations.
        If more pages remain, enqueue the next page automatically.

        All heavy ORM work (partner creation, donations, journal entry)
        happens here — completely outside the HTTP request cycle.
        """
        from datetime import date as date_cls
        PER_PAGE = 100

        history  = self.browse(history_id)
        company  = self.env.company
        wizard   = self.env['api.donation.wizard'].new({})   # transient, no DB row needed

        base_url    = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
        origin_host = urlparse(base_url).hostname or ''
        auth_url    = f"{company.url.rstrip('/')}/api/odoo/auth"
        donate_url  = f"{company.url.rstrip('/')}/api/odoo/donationInfo"

        # Parse dates back from strings (queue_job serialises args as JSON)
        start = date_cls.fromisoformat(start_date) if start_date else None
        end   = date_cls.fromisoformat(end_date)   if end_date   else None

        payload = {"status": "success", "page": page, "perPage": PER_PAGE}
        if start:
            payload["startDate"] = wizard._date_to_iso_z(start, time.min)
        if end:
            payload["endDate"] = wizard._date_to_iso_z(end, time(23, 59, 59))

        wizard._buf_log(f"Job: fetching page {page}", "Pagination", str(payload))
        wizard._flush_logs(history_id)

        page_data = wizard._fetch_donations_from_api(
            auth_url, donate_url, company,
            base_url, origin_host, history,
            override_payload=payload
        )

        if not page_data:
            # Nothing came back — we're done
            history.write({'state': 'done'})
            wizard._buf_log("All pages fetched — history marked done.", 'Completed', '')
            wizard._flush_logs(history_id)
            return

        # ---- Process this page ----
        journal          = self.env['account.journal'].search([('name', 'ilike', 'Bank')], limit=1)
        gateway_config   = self.env['gateway.config'].search([('name', '=', 'Web API')], limit=1)
        company_currency = company.currency_id

        all_data = wizard._prefetch_all_data(page_data, gateway_config, company_currency, history)

        result = wizard._process_donations_bulk(
            page_data, journal, gateway_config, company_currency, all_data, history,
            picking_type_id=picking_type_id,
            source_location_id=source_location_id,
            destination_location_id=destination_location_id,
        )

        if result.get('new_donations') and journal and result.get('accumulators'):
            move = wizard._create_grouped_journal_move(
                journal,
                result['accumulators']['debit'],
                result['accumulators']['credit'],
                company_currency, history
            )
            history.write({
                'journal_entry_id': move.id,
                'picking_id':       result.get('picking_id') or False,
            })
            self.env['api.donation'].browse(result['new_donations']).write({
                'fetch_history_id': history_id
            })

        # Persist next page number
        next_page = page + 1
        history.write({'page': next_page})

        if len(page_data) < PER_PAGE:
            # Last page — mark done
            history.write({'state': 'done'})
            wizard._buf_log("Last page processed — history marked done.", 'Completed', '')
            wizard._flush_logs(history_id)
        else:
            # Enqueue next page
            wizard._buf_log(f"Enqueueing next page {next_page}", 'Pagination', '')
            wizard._flush_logs(history_id)

            self.sudo().with_delay(
                description=f"Donation import – history {history_id} page {next_page}",
                max_retries=3,
                channel='root.donation_import',
            )._run_donation_page_job(
                history_id              = history_id,
                page                    = next_page,
                start_date              = start_date,
                end_date                = end_date,
                picking_type_id         = picking_type_id,
                source_location_id      = source_location_id,
                destination_location_id = destination_location_id,
            )