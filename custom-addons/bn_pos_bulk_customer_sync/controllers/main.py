import base64

from odoo import http
from odoo.http import request

from ..models.pos_config import SLIM_FIELDS  # noqa: F401 (kept for reference/consistency)


class PosBulkCustomerSyncController(http.Controller):

    @http.route("/pos_bulk_customer_sync/snapshot", type="http", auth="user", methods=["GET"])
    def snapshot(self, **kwargs):
        """Full slim snapshot (gzip JSON), regenerated nightly by cron.
        A till fetches this ONCE on first setup, then only calls /delta
        after that. Do not call this on every session open - it defeats
        the purpose of incremental sync.
        """
        attachment = request.env["pos.bulk.customer.sync"].sudo().get_latest_attachment()
        if not attachment:
            return request.make_response(
                "No snapshot generated yet", status=503
            )
        data = base64.b64decode(attachment.datas)
        headers = [
            ("Content-Type", "application/gzip"),
            ("Content-Disposition", 'attachment; filename="customers_snapshot.json.gz"'),
            ("Content-Length", len(data)),
        ]
        return request.make_response(data, headers=headers)

    @http.route("/pos_bulk_customer_sync/delta", type="json", auth="user", methods=["POST"])
    def delta(self, since=None, offset=0, limit=5000, **kwargs):
        """Returns customers created/modified since `since` (ISO datetime
        string), plus a separate list of ids deleted/archived/no-longer-a-
        customer since then, paginated. Call in a loop from the frontend,
        bumping offset, until an empty page comes back.
        """
        Partner = request.env["res.partner"].sudo()
        domain = [("customer_rank", ">", 0), ("active", "=", True)]
        if since:
            domain.append(("write_date", ">", since))

        partners = Partner.search(domain, offset=offset, limit=limit, order="id")
        results = []
        for p in partners:
            pricelist = p.property_product_pricelist
            results.append(
                {
                    "id": p.id,
                    "name": p.name or "",
                    "phone": p.phone or "",
                    "mobile": p.mobile or "",
                    "barcode": p.barcode or "",
                    "pricelist_id": pricelist.id if pricelist else False,
                    "write_date": p.write_date and p.write_date.isoformat(),
                }
            )

        removed_ids = []
        if since:
            # Customers archived or reclassified (no longer customer_rank>0)
            # since last sync need to be pulled out of the local index too.
            stale = Partner.with_context(active_test=False).search(
                [
                    ("write_date", ">", since),
                    "|",
                    ("active", "=", False),
                    ("customer_rank", "=", 0),
                ]
            )
            removed_ids = stale.ids

        return {
            "records": results,
            "removed_ids": removed_ids,
            "has_more": len(partners) == limit,
        }
