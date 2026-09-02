import base64
import gzip
import json

from odoo import fields, models
from odoo.fields import Datetime

# Keep this list short and deliberate - every field added here multiplies
# the payload by 500,000. Only include what the POS UI genuinely needs to
# display and complete a sale.
SLIM_FIELDS = ["id", "name", "phone", "mobile", "barcode", "property_product_pricelist"]


class PosBulkCustomerSync(models.Model):
    _name = "pos.bulk.customer.sync"
    _description = "Tracks/generates the slim customer snapshot used for bulk POS offline sync"

    generated_at = fields.Datetime(required=True, default=fields.Datetime.now)
    attachment_id = fields.Many2one("ir.attachment", required=True)
    partner_count = fields.Integer()

    def _build_partner_dict(self, partner):
        pricelist = partner.property_product_pricelist
        return {
            "id": partner.id,
            "name": partner.name or "",
            "phone": partner.phone or "",
            "mobile": partner.mobile or "",
            "barcode": partner.barcode or "",
            "pricelist_id": pricelist.id if pricelist else False,
            "write_date": Datetime.to_string(partner.write_date),
        }

    def generate_snapshot(self, batch_size=10000):
        """Regenerate the full gzip snapshot of every POS-eligible customer.
        Intended to run nightly via cron (data/ir_cron.xml), NOT on demand
        from 25 tills at once - that reintroduces the exact load-spike
        problem this module exists to avoid.
        """
        Partner = self.env["res.partner"]
        domain = [("customer_rank", ">", 0), ("active", "=", True)]
        all_ids = Partner.search(domain).ids

        records = []
        for i in range(0, len(all_ids), batch_size):
            batch = Partner.browse(all_ids[i : i + batch_size])
            records.extend(self._build_partner_dict(p) for p in batch)

        payload = json.dumps(records).encode("utf-8")
        compressed = gzip.compress(payload)

        attachment = self.env["ir.attachment"].create(
            {
                "name": "pos_bulk_customers_snapshot.json.gz",
                "datas": base64.b64encode(compressed),
                "mimetype": "application/gzip",
                "public": False,
            }
        )
        self.create(
            {
                "attachment_id": attachment.id,
                "partner_count": len(records),
            }
        )
        return attachment

    def get_latest_attachment(self):
        latest = self.search([], order="generated_at desc", limit=1)
        return latest.attachment_id if latest else False
