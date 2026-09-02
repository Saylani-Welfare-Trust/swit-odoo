from odoo import models


class PosSession(models.Model):
    _inherit = "pos.session"

    def _loader_params_res_partner(self):
        """Stock POS pulls the FULL res.partner recordset (every field on the
        model - often 300-400+ fields once accounting, delivery, CRM etc are
        installed) into the frontend at session open. At 500K customers this
        payload is enormous and is exactly what stalls/crashes the till.

        We short-circuit it here so the session-open RPC does not attempt to
        load any customers at all. The frontend instead pulls a slim,
        purpose-built payload via the /pos_bulk_customer_sync/* controller,
        in chunks, in the background (see static/src/js/customer_sync.js).

        NOTE: confirm this method name still matches your installed 17.0.x
        point_of_sale/models/pos_session.py - Odoo has renamed loader hooks
        between minor releases in the past.
        """
        return {
            "search_params": {
                "domain": [("id", "=", 0)],  # matches nothing -> loads 0 partners here
                "fields": ["id"],
            },
        }
