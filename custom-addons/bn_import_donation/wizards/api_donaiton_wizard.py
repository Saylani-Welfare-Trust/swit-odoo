from odoo import models, fields, _
from odoo.exceptions import ValidationError
from datetime import datetime, time, timezone
from collections import defaultdict
import requests
import logging

_logger = logging.getLogger(__name__)


class APIDonationWizard(models.TransientModel):
    _name = 'api.donation.wizard'
    _description = 'API Donation Wizard'

    # =========================================================
    # FIELDS
    # =========================================================

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
        store=True
    )

    destination_location_id = fields.Many2one(
        related='picking_type_id.default_location_dest_id',
        store=True
    )

    # =========================================================
    # BULK LOGGER
    # =========================================================

    def log_batch(self, history, logs):

        if not logs:
            return

        vals_list = []

        for log in logs:
            vals_list.append({
                'fetch_history_id': history.id,
                'name': (log.get('name') or '')[:500],
                'status': log.get('status', 'info'),
                'reason': (log.get('reason') or '')[:3000],
            })

        self.env['fetch.log'].sudo().create(vals_list)

    # =========================================================
    # MAIN ENTRY
    # =========================================================

    def action_fetch_donation(self):

        self.ensure_one()

        logs = []

        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValidationError(
                    _("Start Date must be earlier than End Date.")
                )

        company = self.env.company

        history = self.env['fetch.history'].create({
            'start_date': self.start_date,
            'end_date': self.end_date,
            'page': 1,
            'per_page': 100,
            'state': 'in_progress',
        })

        try:

            logs.append({
                'name': 'Donation import started',
                'status': 'info',
            })

            payload = {
                "status": "success",
                "page": 1,
                "perPage": 100,
            }

            if self.start_date:
                payload['startDate'] = self._date_to_iso_z(
                    self.start_date,
                    time.min
                )

            if self.end_date:
                payload['endDate'] = self._date_to_iso_z(
                    self.end_date,
                    time(23, 59, 59)
                )

            donations = self._fetch_donations_from_api(
                company,
                payload,
                logs
            )

            if not donations:

                history.write({
                    'state': 'completed'
                })

                logs.append({
                    'name': 'No donations returned from API',
                    'status': 'warning',
                })

                self.log_batch(history, logs)

                return True

            logs.append({
                'name': f'Total donations fetched: {len(donations)}',
                'status': 'info',
            })

            journal = self.env['account.journal'].search([
                ('type', '=', 'bank')
            ], limit=1)

            if not journal:
                raise ValidationError(_("No bank journal found."))

            gateway_config = self.env['gateway.config'].search([
                ('name', '=', 'Web API')
            ], limit=1)

            if not gateway_config:
                raise ValidationError(_("Gateway config not found."))

            all_data = self._prefetch_all_data(
                donations,
                gateway_config,
                company,
                logs
            )

            result = self._process_donations_bulk(
                donations,
                journal,
                gateway_config,
                company,
                all_data,
                history,
                logs
            )

            # =====================================================
            # CREATE JOURNAL ENTRY
            # =====================================================

            move = self._create_grouped_journal_move(
                journal,
                result['debit_accumulator'],
                result['credit_accumulator'],
                company.currency_id,
                logs
            )

            if move:

                history.write({
                    'journal_entry_id': move.id
                })

                logs.append({
                    'name': f'Journal Entry Posted: {move.name}',
                    'status': 'success',
                })

            # =====================================================
            # STOCK PICKING
            # =====================================================

            if result.get('picking_id'):

                history.write({
                    'picking_id': result['picking_id']
                })

            history.write({
                'state': 'completed'
            })

            logs.append({
                'name': 'Donation import completed successfully',
                'status': 'success',
            })

            self.log_batch(history, logs)

            return True

        except Exception as e:

            history.write({
                'state': 'completed'
            })

            logs.append({
                'name': 'Donation import failed',
                'status': 'error',
                'reason': str(e),
            })

            self.log_batch(history, logs)

            _logger.exception("Donation Import Failed")

            raise ValidationError(str(e))

    # =========================================================
    # FETCH API
    # =========================================================

    def _fetch_donations_from_api(
        self,
        company,
        payload,
        logs
    ):

        try:

            session = requests.Session()

            auth_url = f"{company.url.rstrip('/')}/api/odoo/auth"
            donate_url = f"{company.url.rstrip('/')}/api/odoo/donationInfo"

            logs.append({
                'name': 'Authenticating API',
                'status': 'info',
            })

            auth_response = session.post(
                auth_url,
                json={
                    "ClientID": company.client_id,
                    "ClientSecret": company.client_secret
                },
                timeout=(30, 120)
            )

            auth_response.raise_for_status()

            token = auth_response.json().get('token')

            if not token:
                raise ValidationError(_("Authentication token missing"))

            session.headers.update({
                'authorization': f'bearer {token}'
            })

            logs.append({
                'name': 'Fetching donations from API',
                'status': 'info',
            })

            response = session.post(
                donate_url,
                json=payload,
                timeout=(30, 300)
            )

            response.raise_for_status()

            data = response.json()

            return data.get('donationsInfo', [])

        except requests.exceptions.Timeout:
            raise ValidationError(
                _("API timeout. Server took too long to respond.")
            )

        except Exception as e:
            raise ValidationError(
                _("API Error: %s") % str(e)
            )

    # =========================================================
    # PREFETCH
    # =========================================================

    def _prefetch_all_data(
        self,
        donations,
        gateway_config,
        company,
        logs
    ):

        currencies = set()
        import_ids = set()
        mobiles = set()

        for donation in donations:

            if donation.get('currency'):
                currencies.add(
                    donation.get('currency')
                )

            if donation.get('_id'):
                import_ids.add(
                    donation.get('_id')
                )

            donor = donation.get('donor_details') or {}

            if donor.get('phone'):
                mobiles.add(
                    donor.get('phone')[-10:]
                )

        currency_records = self.env['res.currency'].search([
            ('name', 'in', list(currencies))
        ])

        currency_map = {
            c.name.lower(): c
            for c in currency_records
        }

        existing_imports = self.env['api.donation'].search_read(
            [('import_id', 'in', list(import_ids))],
            ['import_id']
        )

        existing_import_ids = {
            x['import_id']
            for x in existing_imports
        }

        existing_partners = self.env['res.partner'].search_read(
            [('mobile', 'in', list(mobiles))],
            ['mobile']
        )

        partner_map = {}

        for p in existing_partners:
            partner_map[p['mobile']] = p['id']

        gateway_currency_lines = {}

        for line in gateway_config.gateway_config_currency_ids:

            if line.currency_id and line.account_id:

                gateway_currency_lines[
                    line.currency_id.name.lower()
                ] = line.account_id.id

        gateway_product_lines = {}

        for line in gateway_config.gateway_config_line_ids:

            key = (line.name or '').strip().lower()

            account_id = (
                line.product_id.property_account_income_id.id
                or line.product_id.categ_id.property_account_income_categ_id.id
            )

            gateway_product_lines[key] = {
                'product_id': line.product_id.id,
                'account_id': account_id,
            }

        logs.append({
            'name': 'Prefetch completed',
            'status': 'success',
        })

        return {
            'currency_map': currency_map,
            'existing_import_ids': existing_import_ids,
            'partner_map': partner_map,
            'gateway_currency_lines': gateway_currency_lines,
            'gateway_product_lines': gateway_product_lines,
        }

    # =========================================================
    # PROCESS DONATIONS
    # =========================================================

    def _process_donations_bulk(
        self,
        donations,
        journal,
        gateway_config,
        company,
        all_data,
        history,
        logs
    ):

        donations_vals = []

        debit_accumulator = defaultdict(float)
        credit_accumulator = defaultdict(float)

        stock_accumulator = defaultdict(float)

        partner_create_vals = []

        partner_cache = all_data['partner_map']

        for donation in donations:

            import_id = donation.get('_id')

            if import_id in all_data['existing_import_ids']:
                continue

            if donation.get('status') != 'success':
                continue

            donor = donation.get('donor_details') or {}

            mobile = donor.get('phone', '')[-10:]

            partner_id = partner_cache.get(mobile)

            # =================================================
            # CREATE PARTNER
            # =================================================

            if not partner_id and mobile:

                existing = next(
                    (
                        p for p in partner_create_vals
                        if p.get('mobile') == mobile
                    ),
                    False
                )

                if not existing:

                    partner_create_vals.append({
                        'name': donor.get('name'),
                        'mobile': mobile,
                        'email': donor.get('email'),
                    })

            currency_name = (
                donation.get('currency') or ''
            ).lower()

            total_amount = float(
                donation.get('total_amount', 0)
            ) - float(
                donation.get('bank_charges', 0)
            )

            donation_vals = {
                'import_id': import_id,
                'name': donor.get('name'),
                'phone': donor.get('phone'),
                'email': donor.get('email'),
                'currency': currency_name,
                'total_amount': total_amount,
                'fetch_history_id': history.id,
            }

            if partner_id:
                donation_vals['donor_id'] = partner_id

            # =================================================
            # DONATION ITEMS
            # =================================================

            donation_items = []

            for item in donation.get('items', []):

                item_name = ''
                type_name = ''
                donation_type = item.get('donationType', '')

                if isinstance(item.get('item'), dict):

                    item_name = item.get(
                        'item',
                        {}
                    ).get(
                        'en',
                        {}
                    ).get(
                        'name',
                        ''
                    )

                if isinstance(item.get('type'), dict):

                    type_name = item.get(
                        'type',
                        {}
                    ).get(
                        'en',
                        {}
                    ).get(
                        'name',
                        ''
                    )

                donation_items.append((0, 0, {
                    'item': item_name,
                    'qty': item.get('qty'),
                    'price': item.get('price'),
                    'total': item.get('total'),
                    'type': type_name,
                    'donation_type': donation_type,
                }))

                # =============================================
                # PRODUCT KEY
                # =============================================

                product_key = (
                    f"{donation_type}"
                    f"{item_name}"
                    f"{type_name}"
                ).strip().lower()

                config = all_data[
                    'gateway_product_lines'
                ].get(product_key)

                if not config:

                    logs.append({
                        'name': f'Product config missing',
                        'status': 'warning',
                        'reason': product_key,
                    })

                    continue

                product = self.env[
                    'product.product'
                ].browse(
                    config['product_id']
                )

                # =============================================
                # STOCK
                # =============================================

                if (
                    product
                    and product.detailed_type == 'product'
                ):

                    qty = float(
                        item.get('qty') or 1
                    )

                    stock_accumulator[
                        product.id
                    ] += qty

                # =============================================
                # ACCOUNTING
                # =============================================

                account_id = config.get(
                    'account_id'
                )

                debit_account = all_data[
                    'gateway_currency_lines'
                ].get(currency_name)

                total = float(
                    item.get('total') or 0
                )

                if debit_account:
                    debit_accumulator[
                        debit_account
                    ] += total

                if account_id:
                    credit_accumulator[
                        account_id
                    ] += total

            donation_vals[
                'donation_item_ids'
            ] = donation_items

            donations_vals.append(
                donation_vals
            )

        # =====================================================
        # CREATE PARTNERS
        # =====================================================

        if partner_create_vals:

            created_partners = self.env[
                'res.partner'
            ].create(
                partner_create_vals
            )

            for partner in created_partners:
                partner_cache[
                    partner.mobile
                ] = partner.id

            logs.append({
                'name': f'Partners Created: {len(created_partners)}',
                'status': 'success',
            })

        # =====================================================
        # ASSIGN PARTNERS
        # =====================================================

        for vals in donations_vals:

            if not vals.get('donor_id'):

                mobile = (
                    vals.get('phone', '')[-10:]
                )

                vals['donor_id'] = (
                    partner_cache.get(mobile)
                )

        # =====================================================
        # CREATE DONATIONS
        # =====================================================

        created_donations = self.env[
            'api.donation'
        ].create(
            donations_vals
        )

        logs.append({
            'name': f'Donations Created: {len(created_donations)}',
            'status': 'success',
        })

        # =====================================================
        # STOCK PICKING
        # =====================================================

        picking = False

        if stock_accumulator:

            if not self.picking_type_id:
                raise ValidationError(
                    _("Picking Type missing.")
                )

            picking = self.env[
                'stock.picking'
            ].create({
                'picking_type_id': self.picking_type_id.id,
                'location_id': self.source_location_id.id,
                'location_dest_id': self.destination_location_id.id,
                'origin': f'Donation Import {fields.Date.today()}',
            })

            move_vals = []

            for product_id, qty in stock_accumulator.items():

                product = self.env[
                    'product.product'
                ].browse(product_id)

                move_vals.append({
                    'name': product.display_name,
                    'product_id': product.id,
                    'product_uom_qty': qty,
                    'quantity': qty,
                    'product_uom': product.uom_id.id,
                    'location_id': self.source_location_id.id,
                    'location_dest_id': self.destination_location_id.id,
                    'picking_id': picking.id,
                })

            self.env['stock.move'].create(
                move_vals
            )

            try:

                picking.action_confirm()
                picking.action_assign()

                for move in picking.move_ids:
                    move.quantity = move.product_uom_qty

                picking.button_validate()

                logs.append({
                    'name': f'Stock Picking Posted: {picking.name}',
                    'status': 'success',
                })

            except Exception as e:

                logs.append({
                    'name': 'Stock Picking Failed',
                    'status': 'error',
                    'reason': str(e),
                })

                _logger.exception(
                    "Stock Picking Error"
                )

        return {
            'created_donations': created_donations.ids,
            'debit_accumulator': debit_accumulator,
            'credit_accumulator': credit_accumulator,
            'picking_id': picking.id if picking else False,
        }

    # =========================================================
    # JOURNAL ENTRY
    # =========================================================

    def _create_grouped_journal_move(
        self,
        journal,
        debit_accumulator,
        credit_accumulator,
        company_currency,
        logs
    ):

        lines = []

        total_debit = 0.0
        total_credit = 0.0

        # =====================================================
        # DEBIT
        # =====================================================

        for account_id, amount in debit_accumulator.items():

            amount = round(amount, 2)

            if not amount:
                continue

            total_debit += amount

            lines.append((0, 0, {
                'account_id': account_id,
                'debit': amount,
                'credit': 0.0,
                'name': 'Donation Import Debit',
            }))

        # =====================================================
        # CREDIT
        # =====================================================

        for account_id, amount in credit_accumulator.items():

            amount = round(amount, 2)

            if not amount:
                continue

            total_credit += amount

            lines.append((0, 0, {
                'account_id': account_id,
                'debit': 0.0,
                'credit': amount,
                'name': 'Donation Import Credit',
            }))

        if not lines:

            logs.append({
                'name': 'No journal lines generated',
                'status': 'warning',
            })

            return False

        # =====================================================
        # BALANCE FIX
        # =====================================================

        diff = round(
            total_debit - total_credit,
            2
        )

        if diff != 0:

            if not journal.default_account_id:
                raise ValidationError(
                    _("Journal missing default account.")
                )

            if diff > 0:

                lines.append((0, 0, {
                    'account_id': journal.default_account_id.id,
                    'debit': 0.0,
                    'credit': abs(diff),
                    'name': 'Rounding Adjustment',
                }))

            else:

                lines.append((0, 0, {
                    'account_id': journal.default_account_id.id,
                    'debit': abs(diff),
                    'credit': 0.0,
                    'name': 'Rounding Adjustment',
                }))

        move = self.env[
            'account.move'
        ].create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': fields.Date.today(),
            'ref': f'Donation Import {fields.Date.today()}',
            'line_ids': lines,
        })

        try:

            move.action_post()

        except Exception as e:

            logs.append({
                'name': 'Journal posting failed',
                'status': 'error',
                'reason': str(e),
            })

            _logger.exception(
                "Journal Posting Failed"
            )

            raise ValidationError(
                _("Journal posting failed: %s") % str(e)
            )

        return move

    # =========================================================
    # HELPERS
    # =========================================================

    def _date_to_iso_z(self, date_val, t):

        dt = datetime.combine(
            date_val,
            t
        ).replace(
            tzinfo=timezone.utc
        )

        return dt.isoformat(
            timespec='milliseconds'
        ).replace(
            '+00:00',
            'Z'
        )