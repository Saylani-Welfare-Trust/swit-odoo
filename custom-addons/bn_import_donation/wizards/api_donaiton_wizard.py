from odoo import models, fields, _
from odoo.exceptions import ValidationError

from datetime import datetime, time, timezone
from urllib.parse import urlparse

from collections import defaultdict

import requests
import logging

_logger = logging.getLogger(__name__)


class APIDonationWizard(models.TransientModel):
    _name = 'api.donation.wizard'
    _description = 'API Donation Wizard'


    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')


    # =====================================================
    # MAIN
    # =====================================================

    def action_fetch_donation(self):
        self.ensure_one()

        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValidationError(
                    _("Start Date must be less than End Date.")
                )

        company = self.env.company

        if not company.url:
            raise ValidationError(_("Company URL not configured."))

        if not company.client_id:
            raise ValidationError(_("Client ID not configured."))

        if not company.client_secret:
            raise ValidationError(_("Client Secret not configured."))

        # =====================================================
        # URLS
        # =====================================================

        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url'
        ) or ''

        parsed = urlparse(base_url)

        auth_url = f"{company.url.rstrip('/')}/api/odoo/auth"
        donation_url = f"{company.url.rstrip('/')}/api/odoo/donationInfo"

        # =====================================================
        # SESSION
        # =====================================================

        session = requests.Session()

        session.headers.update({
            'Origin': base_url,
            'x-forwarded-for': parsed.hostname or '',
            'Content-Type': 'application/json',
        })

        # =====================================================
        # AUTHENTICATE
        # =====================================================

        token = self._authenticate(
            session=session,
            url=auth_url,
            client_id=company.client_id,
            client_secret=company.client_secret,
        )

        session.headers.update({
            'authorization': f'bearer {token}'
        })

        # =====================================================
        # PAYLOAD
        # =====================================================

        payload = {
            'status': 'success'
        }

        if self.start_date:
            payload['startDate'] = self._date_to_iso_z(
                self.start_date
            )

        if self.end_date:
            payload['endDate'] = self._date_to_iso_z(
                self.end_date
            )

        # =====================================================
        # FETCH DONATIONS
        # =====================================================

        donations_info = self._fetch_donations(
            session=session,
            url=donation_url,
            payload=payload,
        )

        if not donations_info:
            return True

        # =====================================================
        # MODELS
        # =====================================================

        Donation = self.env['api.donation'].with_context(
            tracking_disable=True,
            mail_create_nolog=True,
            mail_notrack=True,
        )

        Partner = self.env['res.partner']
        Currency = self.env['res.currency']
        Country = self.env['res.country']

        # =====================================================
        # PREFETCH EXISTING IMPORT IDS
        # =====================================================

        all_import_ids = list({
            info.get('_id')
            for info in donations_info
            if info.get('_id')
        })

        existing_import_ids = set(
            Donation.search([
                ('import_id', 'in', all_import_ids)
            ]).mapped('import_id')
        )

        # =====================================================
        # CONFIGS
        # =====================================================

        journal = self.env['account.journal'].search([
            ('name', 'ilike', 'Bank')
        ], limit=1)

        gateway_config = self.env['gateway.config'].search([
            ('name', '=', 'Web API')
        ], limit=1)

        company_currency = self.env.company.currency_id

        # =====================================================
        # CACHES
        # =====================================================

        currency_cache = {}
        conversion_cache = {}
        country_cache = {}
        partner_cache = {}

        donor_category_id = self.env.ref(
            'bn_profile_management.donor_partner_category'
        ).id

        individual_category_id = self.env.ref(
            'bn_profile_management.individual_partner_category'
        ).id

        # =====================================================
        # PRODUCT CONFIG CACHE
        # =====================================================

        product_config_cache = {}

        if gateway_config:
            product_config_cache = {
                line.name: line
                for line in gateway_config.gateway_config_line_ids
            }

        # =====================================================
        # DEBIT ACCOUNT CACHE
        # =====================================================

        debit_account_cache = {}

        if gateway_config:
            for line in gateway_config.gateway_config_currency_ids:
                debit_account_cache[line.currency_id.id] = line.account_id.id

        # =====================================================
        # ACCUMULATORS
        # =====================================================

        debit_accumulator = defaultdict(
            lambda: {
                'debit_base': 0.0,
                'amount_currency': 0.0,
            }
        )

        credit_accumulator = defaultdict(
            lambda: {
                'credit_base': 0.0,
                'amount_currency': 0.0,
                'analytic_account_id': False,
            }
        )

        # =====================================================
        # DONATION VALUES
        # =====================================================

        donation_vals_list = []

        # =====================================================
        # LOOP
        # =====================================================

        for info in donations_info:

            import_id = info.get('_id')

            if not import_id:
                continue

            if import_id in existing_import_ids:
                continue

            if info.get('status') != 'success':
                continue

            currency_name = info.get('currency') or ''

            conversion_rate = self._get_conversion_rate(
                currency_name=currency_name,
                currency_cache=currency_cache,
                conversion_cache=conversion_cache,
            )

            # =====================================================
            # DONOR
            # =====================================================

            donor = info.get('donor_details') or {}

            donor_id = False

            donor_name = donor.get('name') or ''
            donor_phone = (donor.get('phone') or '')[-10:]
            donor_country_code = donor.get('country') or ''

            country_id = False

            if donor_country_code:

                country_id = country_cache.get(
                    donor_country_code
                )

                if country_id is None:

                    country_id = Country.search([
                        ('code', '=', donor_country_code)
                    ], limit=1).id

                    country_cache[donor_country_code] = country_id

            if donor_name:

                partner_key = (
                    f"{country_id}_{donor_phone}"
                )

                donor_partner = partner_cache.get(
                    partner_key
                )

                if donor_partner is None:

                    donor_partner = Partner.search([
                        ('country_code_id', '=', country_id),
                        ('mobile', '=', donor_phone),
                        ('category_id', 'in', [donor_category_id]),
                    ], limit=1)

                    partner_cache[partner_key] = donor_partner

                if donor_partner:
                    donor_id = donor_partner.id

                else:

                    donor_partner = Partner.create({
                        'name': donor_name,
                        'mobile': donor_phone,
                        'email': donor.get('email', ''),
                        'country_code_id': country_id,
                        'category_id': [(6, 0, [
                            donor_category_id,
                            individual_category_id,
                        ])]
                    })

                    donor_partner.action_register()

                    donor_id = donor_partner.id

                    partner_cache[partner_key] = donor_partner

            else:

                donor_id = Partner.search([
                    ('primary_registration_id', '=', '2025-9999998-9')
                ], limit=1).id

            # =====================================================
            # TOTALS
            # =====================================================

            total_amount = float(
                info.get('total_amount', 0) or 0
            )

            total_amount_local = (
                total_amount * conversion_rate
                if currency_name != 'PKR'
                else total_amount
            )

            # =====================================================
            # DONATION VALUES
            # =====================================================

            donation_vals = {
                'import_id': import_id,
                'remarks': info.get('remarks', ''),
                'total_amount': total_amount,
                'total_amount_local': total_amount_local,
                'donor': info.get('donor', ''),
                'donation_type': info.get('donation_type', ''),
                'donation_from': info.get('donation_from', ''),
                'dn_number': info.get('DN_Number', ''),
                'subscription_interval': info.get(
                    'subscriptionInterval', ''
                ),
                'is_recurring': info.get(
                    'isRecurring', False
                ),
                'response_code': info.get(
                    'response_code', ''
                ),
                'response_description': info.get(
                    'response_description', ''
                ),
                'currency': currency_name,
                'referer': info.get('referer', ''),
                'website': info.get('website', ''),
                'account_source': info.get(
                    'account_source', ''
                ),
                'conversion_rate': conversion_rate,
                'bank_charges': info.get(
                    'bank_charges', 0
                ),
                'bank_charges_in_text': info.get(
                    'bank_charges_in_text', ''
                ),
                'blinq_notification_number': info.get(
                    'blinq_notification_number', ''
                ),
                'created_at': self._parse_iso_to_dt(
                    info.get('createdAt')
                ),
                'updated_at': self._parse_iso_to_dt(
                    info.get('updatedAt')
                ),
                'donation_id': info.get(
                    'donation_id', ''
                ),
                'invoice_id': info.get(
                    'invoice_id', ''
                ),
                'transaction_id': info.get(
                    'transaction_id', ''
                ),

                # DONOR
                'name': donor.get('name', ''),
                'phone': donor.get('phone', ''),
                'email': donor.get('email', ''),
                'cnic': donor.get('cnic', ''),
                'country': donor.get('country', ''),
                'ip_address': donor.get('ipAddress', ''),
                'subscription_for_news': donor.get(
                    'subscriptionForNews', False
                ),
                'subscription_for_whatsapp': donor.get(
                    'subscriptionForWhatsapp', False
                ),
                'subscription_for_sms': donor.get(
                    'subscriptionForSms', False
                ),
                'qurbani_country': donor.get(
                    'qurbaniCountry', ''
                ),
                'qurbani_city': donor.get(
                    'qurbaniCity', ''
                ),
                'qurbani_day': donor.get(
                    'qurbaniDay', ''
                ),
                'donor_id': donor_id,
            }

            # =====================================================
            # ITEMS
            # =====================================================

            item_lines = []

            items = info.get('items') or []

            currency_rec = currency_cache.get(
                currency_name
            )

            if currency_rec is None:

                currency_rec = Currency.search([
                    ('name', '=', currency_name)
                ], limit=1)

                currency_cache[currency_name] = currency_rec

            is_foreign = (
                currency_rec != company_currency
            )

            debit_account_id = debit_account_cache.get(
                currency_rec.id
            )

            for item in items:

                type_data = item.get('type') or {}
                item_data = item.get('item') or {}

                type_name = (
                    type_data.get('en', {}).get('name', '')
                    if isinstance(type_data, dict)
                    else ''
                )

                item_name = (
                    item_data.get('en', {}).get('name', '')
                    if isinstance(item_data, dict)
                    else ''
                )

                item_total = float(
                    item.get('total', 0) or 0
                )

                item_vals = {
                    'donation_type': item.get(
                        'donationType', ''
                    ),
                    'total': item_total,
                    'price': item.get('price', 0),
                    'price_id': item.get('price_id', 0),
                    'qty': item.get('qty', 0),
                    'type': type_name,
                    'item': item_name,
                    'donation_no': item.get(
                        'donationNo', 0
                    ),
                    'is_priced_item': item.get(
                        'isPricedItem', False
                    ),
                }

                item_lines.append((0, 0, item_vals))

                # =====================================================
                # JOURNAL ACCUMULATION
                # =====================================================

                if not gateway_config:
                    continue

                if not debit_account_id:
                    continue

                product_key = (
                    f"{item.get('donationType', '')}"
                    f"{item_name}"
                    f"{type_name}"
                )

                config_line = product_config_cache.get(
                    product_key
                )

                if not config_line:
                    continue

                credit_account = config_line.account_id

                if not credit_account:
                    continue

                analytic_id = (
                    config_line.analytic_account_id.id
                    if config_line.analytic_account_id
                    else False
                )

                item_total_base = (
                    item_total * conversion_rate
                    if is_foreign
                    else item_total
                )

                # DEBIT

                debit_key = (
                    debit_account_id,
                    currency_rec.id
                )

                debit_accumulator[debit_key][
                    'debit_base'
                ] = round(
                    debit_accumulator[debit_key][
                        'debit_base'
                    ] + item_total_base,
                    2
                )

                if is_foreign:

                    debit_accumulator[debit_key][
                        'amount_currency'
                    ] = round(
                        debit_accumulator[debit_key][
                            'amount_currency'
                        ] + item_total,
                        2
                    )

                # CREDIT

                credit_key = (
                    credit_account.id,
                    currency_rec.id,
                    analytic_id,
                )

                credit_accumulator[credit_key][
                    'credit_base'
                ] = round(
                    credit_accumulator[credit_key][
                        'credit_base'
                    ] + item_total_base,
                    2
                )

                if is_foreign:

                    credit_accumulator[credit_key][
                        'amount_currency'
                    ] = round(
                        credit_accumulator[credit_key][
                            'amount_currency'
                        ] - item_total,
                        2
                    )

                credit_accumulator[credit_key][
                    'analytic_account_id'
                ] = analytic_id

            donation_vals[
                'donation_item_ids'
            ] = item_lines

            donation_vals_list.append(
                donation_vals
            )

        # =====================================================
        # CREATE DONATIONS
        # =====================================================

        if not donation_vals_list:
            return True

        donations = Donation.create(
            donation_vals_list
        )

        # =====================================================
        # CREATE JOURNAL ENTRY
        # =====================================================

        move = False

        if (
            gateway_config
            and journal
            and (
                debit_accumulator
                or credit_accumulator
            )
        ):

            move = self._create_grouped_journal_move(
                journal=journal,
                debit_accumulator=debit_accumulator,
                credit_accumulator=credit_accumulator,
                company_currency=company_currency,
            )

        # =====================================================
        # FETCH HISTORY
        # =====================================================

        fetch_history = self.env[
            'fetch.history'
        ].create({
            'start_date': self.start_date,
            'end_date': self.end_date,
            'journal_entry_id': move.id if move else False,
        })

        donations.write({
            'fetch_history_id': fetch_history.id
        })

        return True


    # =====================================================
    # AUTHENTICATION
    # =====================================================

    def _authenticate(
        self,
        session,
        url,
        client_id,
        client_secret
    ):

        try:

            response = session.post(
                url,
                json={
                    "ClientID": client_id,
                    "ClientSecret": client_secret
                },
                timeout=30
            )

            response.raise_for_status()

            data = response.json()

        except requests.exceptions.RequestException as e:

            _logger.exception(
                'Authentication failed'
            )

            raise ValidationError(
                _('Authentication failed: %s') % str(e)
            )

        token = data.get('token')

        if not token:
            raise ValidationError(
                _('Token not found.')
            )

        return token


    # =====================================================
    # FETCH DONATIONS
    # =====================================================

    def _fetch_donations(
        self,
        session,
        url,
        payload
    ):

        try:

            response = session.post(
                url,
                json=payload,
                timeout=60
            )

            response.raise_for_status()

            data = response.json()

        except requests.exceptions.RequestException as e:

            _logger.exception(
                'Donation API failed'
            )

            raise ValidationError(
                _('Donation fetch failed: %s') % str(e)
            )

        if not isinstance(data, dict):
            raise ValidationError(
                _('Invalid donation response.')
            )

        return data.get('donationsInfo') or []


    # =====================================================
    # DATE HELPERS
    # =====================================================

    def _date_to_iso_z(self, date_val):

        dt = datetime.combine(
            date_val,
            time.min
        ).replace(
            tzinfo=timezone.utc
        )

        return dt.isoformat(
            timespec='milliseconds'
        ).replace('+00:00', 'Z')


    def _parse_iso_to_dt(self, iso_str):

        if not iso_str:
            return False

        try:

            return datetime.fromisoformat(
                iso_str.replace('Z', '+00:00')
            ).replace(tzinfo=None)

        except Exception:

            try:

                clean = (
                    iso_str.split('.')[0]
                    .replace('T', ' ')
                )

                return datetime.strptime(
                    clean,
                    '%Y-%m-%d %H:%M:%S'
                )

            except Exception:

                return False


    # =====================================================
    # CURRENCY CONVERSION
    # =====================================================

    def _get_conversion_rate(
        self,
        currency_name,
        currency_cache,
        conversion_cache
    ):

        if not currency_name:
            return 1.0

        if currency_name in conversion_cache:
            return conversion_cache[currency_name]

        currency = currency_cache.get(
            currency_name
        )

        if currency is None:

            currency = self.env[
                'res.currency'
            ].search([
                ('name', '=', currency_name)
            ], limit=1)

            currency_cache[currency_name] = currency

        conversion_rate = 1.0

        if currency:

            rate = self.env[
                'res.currency.rate'
            ].search([
                ('currency_id', '=', currency.id)
            ], order='name desc', limit=1)

            conversion_rate = (
                rate.inverse_company_rate
                or 1.0
            )

        conversion_cache[
            currency_name
        ] = conversion_rate

        return conversion_rate


    # =====================================================
    # JOURNAL ENTRY
    # =====================================================

    def _create_grouped_journal_move(
        self,
        journal,
        debit_accumulator,
        credit_accumulator,
        company_currency
    ):

        company_currency_id = (
            company_currency.id
        )

        journal_lines = []

        debit_total = 0.0
        credit_total = 0.0

        # =====================================================
        # DEBIT LINES
        # =====================================================

        for (
            account_id,
            currency_id
        ), vals in debit_accumulator.items():

            debit_amount = round(
                vals.get('debit_base', 0.0),
                2
            )

            debit_total += debit_amount

            line_vals = {
                'account_id': account_id,
                'name': 'Donation Import Debit',
                'debit': debit_amount,
                'credit': 0.0,
            }

            if currency_id != company_currency_id:

                line_vals['currency_id'] = (
                    currency_id
                )

                line_vals['amount_currency'] = round(
                    vals.get(
                        'amount_currency',
                        0.0
                    ),
                    2
                )

            journal_lines.append(
                (0, 0, line_vals)
            )

        # =====================================================
        # CREDIT LINES
        # =====================================================

        for (
            account_id,
            currency_id,
            analytic_id
        ), vals in credit_accumulator.items():

            credit_amount = round(
                vals.get('credit_base', 0.0),
                2
            )

            credit_total += credit_amount

            line_vals = {
                'account_id': account_id,
                'name': 'Donation Import Credit',
                'debit': 0.0,
                'credit': credit_amount,
            }

            if currency_id != company_currency_id:

                line_vals['currency_id'] = (
                    currency_id
                )

                line_vals['amount_currency'] = round(
                    vals.get(
                        'amount_currency',
                        0.0
                    ),
                    2
                )

            if analytic_id:

                line_vals[
                    'analytic_distribution'
                ] = {
                    str(analytic_id): 100
                }

            journal_lines.append(
                (0, 0, line_vals)
            )

        # =====================================================
        # DIFFERENCE
        # =====================================================

        difference = round(
            debit_total - credit_total,
            2
        )

        if abs(difference) >= 0.01:

            difference_account = self.env[
                'account.account'
            ].search([
                (
                    'code',
                    '=',
                    self.env.company.difference_account_prefix
                )
            ], limit=1)

            if not difference_account:

                raise ValidationError(
                    _("Difference account not found.")
                )

            journal_lines.append((0, 0, {
                'account_id': difference_account.id,
                'name': 'Difference Adjustment',
                'debit': abs(difference)
                if difference < 0 else 0.0,
                'credit': difference
                if difference > 0 else 0.0,
            }))

        # =====================================================
        # CREATE MOVE
        # =====================================================

        move = self.env[
            'account.move'
        ].sudo().create({
            'move_type': 'entry',
            'ref': f"Donation Import {fields.Datetime.now()}",
            'date': fields.Date.today(),
            'journal_id': journal.id,
            'line_ids': journal_lines,
        })

        move.action_post()

        return move