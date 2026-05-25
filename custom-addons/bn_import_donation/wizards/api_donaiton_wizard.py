from odoo import models, fields, _
from odoo.exceptions import ValidationError
from datetime import datetime, time, timezone
from collections import defaultdict
import requests
import logging

_logger = logging.getLogger(__name__)


class APIDonationWizard(models.TransientModel):
    _name = 'api.donation.wizard'
    _description = 'API Donation Wizard (Production Safe)'

    # =========================================================
    # FIELDS
    # =========================================================
    start_date = fields.Date()
    end_date = fields.Date()

    picking_type_id = fields.Many2one(
        'stock.picking.type',
        default=lambda self: self.env.ref(
            'bn_import_donation.online_donation_stock_picking_type',
            raise_if_not_found=False
        )
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
    # ENTRY POINT
    # =========================================================
    def action_fetch_donation(self):
        self.ensure_one()

        company = self.env.company
        journal = self.env['account.journal'].search([('type', '=', 'bank')], limit=1)
        if not journal:
            raise ValidationError(_("Bank journal not found"))

        gateway_config = self.env['gateway.config'].search([('name', '=', 'Web API')], limit=1)

        payload = {
            "status": "success",
            "page": 1,
            "perPage": 100,
        }

        if self.start_date:
            payload["startDate"] = self._to_utc(self.start_date, time.min)
        if self.end_date:
            payload["endDate"] = self._to_utc(self.end_date, time(23, 59, 59))

        donations = self._fetch(company, payload)

        if not donations:
            return True

        all_data = self._prefetch(donations, gateway_config)

        result = self._process(donations, all_data, journal)

        move = self._create_journal(
            journal,
            result["debit"],
            result["credit"],
            company.currency_id
        )

        picking = self._create_stock(result["stock"])

        return {
            "journal_id": move.id if move else False,
            "picking_id": picking.id if picking else False,
        }

    # =========================================================
    # API
    # =========================================================
    def _fetch(self, company, payload):
        session = requests.Session()

        auth = session.post(
            f"{company.url}/api/odoo/auth",
            json={
                "ClientID": company.client_id,
                "ClientSecret": company.client_secret
            },
            timeout=30
        )

        auth.raise_for_status()
        token = auth.json().get("token")

        if not token:
            raise ValidationError(_("Auth token missing"))

        session.headers.update({"authorization": f"bearer {token}"})

        res = session.post(
            f"{company.url}/api/odoo/donationInfo",
            json=payload,
            timeout=120
        )

        res.raise_for_status()
        return res.json().get("donationsInfo", [])

    # =========================================================
    # PREFETCH
    # =========================================================
    def _prefetch(self, donations, gateway_config):

        import_ids = {d.get("_id") for d in donations}
        mobiles = {d.get("donor_details", {}).get("phone", "")[-10:] for d in donations}

        existing = self.env['api.donation'].search_read(
            [('import_id', 'in', list(import_ids))],
            ['import_id']
        )

        existing_ids = {x['import_id'] for x in existing}

        partners = self.env['res.partner'].search_read(
            [('mobile', 'in', list(mobiles))],
            ['id', 'mobile']
        )

        partner_map = {p['mobile']: p['id'] for p in partners}

        currency_map = {
            c.name.lower(): c for c in self.env['res.currency'].search([])
        }

        gateway_currency = {}
        gateway_products = {}

        if gateway_config:
            for l in gateway_config.gateway_config_currency_ids:
                if l.currency_id:
                    gateway_currency[l.currency_id.name.lower()] = l.account_id.id

            for l in gateway_config.gateway_config_line_ids:
                gateway_products[(l.name or "").lower()] = {
                    "product_id": l.product_id.id,
                    "account_id": l.product_id.property_account_income_id.id
                }

        return {
            "existing": existing_ids,
            "partners": partner_map,
            "currency": currency_map,
            "gw_currency": gateway_currency,
            "gw_product": gateway_products
        }

    # =========================================================
    # PROCESS
    # =========================================================
    def _process(self, donations, data, journal):

        debit = defaultdict(float)
        credit = defaultdict(float)
        stock = defaultdict(float)

        for d in donations:

            if d.get("_id") in data["existing"]:
                continue

            donor = d.get("donor_details") or {}
            mobile = donor.get("phone", "")[-10:]

            currency = (d.get("currency") or "").lower()

            total = float(d.get("total_amount") or 0)

            partner_id = data["partners"].get(mobile)

            # DONATION
            self.env['api.donation'].create({
                "import_id": d.get("_id"),
                "name": donor.get("name"),
                "phone": donor.get("phone"),
                "email": donor.get("email"),
                "total_amount": total,
                "currency": currency,
                "donor_id": partner_id,
            })

            for item in d.get("items", []):

                name = (item.get("item", {}).get("en", {}).get("name") or "").lower()

                config = data["gw_product"].get(name)

                if not config:
                    continue

                qty = float(item.get("qty") or 1)
                amount = float(item.get("total") or 0)

                debit[data["gw_currency"].get(currency)] += amount
                credit[config["account_id"]] += amount

                stock[config["product_id"]] += qty

        return {
            "debit": debit,
            "credit": credit,
            "stock": stock
        }

    # =========================================================
    # JOURNAL (FIXED - NO SECONDARY CURRENCY ISSUE)
    # =========================================================
    def _create_journal(self, journal, debit, credit, company_currency):

        lines = []

        for acc, amt in debit.items():
            if not acc or not amt:
                continue

            lines.append((0, 0, {
                "account_id": acc,
                "debit": amt,
                "credit": 0.0,
                "name": "Donation Debit",
                "currency_id": False,   # 🔥 IMPORTANT FIX
            }))

        for acc, amt in credit.items():
            if not acc or not amt:
                continue

            lines.append((0, 0, {
                "account_id": acc,
                "debit": 0.0,
                "credit": amt,
                "name": "Donation Credit",
                "currency_id": False,   # 🔥 FIX SECONDARY CURRENCY ERROR
            }))

        if not lines:
            return False

        move = self.env['account.move'].create({
            "move_type": "entry",
            "journal_id": journal.id,
            "line_ids": lines,
        })

        move.action_post()
        return move

    # =========================================================
    # STOCK PICKING (FIXED)
    # =========================================================
    def _create_stock(self, stock_data):

        if not stock_data:
            return False

        picking = self.env['stock.picking'].create({
            "picking_type_id": self.picking_type_id.id,
            "location_id": self.source_location_id.id,
            "location_dest_id": self.destination_location_id.id,
            "origin": "Donation Import"
        })

        for product_id, qty in stock_data.items():

            product = self.env['product.product'].browse(product_id)

            self.env['stock.move'].create({
                "name": product.display_name,
                "product_id": product.id,
                "product_uom_qty": qty,
                "product_uom": product.uom_id.id,
                "picking_id": picking.id,
                "location_id": self.source_location_id.id,
                "location_dest_id": self.destination_location_id.id,
            })

        picking.action_confirm()
        picking.action_assign()
        picking.button_validate()

        return picking

    # =========================================================
    # HELPERS
    # =========================================================
    def _to_utc(self, d, t):
        return datetime.combine(d, t).replace(tzinfo=timezone.utc).isoformat()