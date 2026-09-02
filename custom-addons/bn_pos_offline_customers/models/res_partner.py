from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def get_pos_customers_light(self, offset=0, limit=5000, last_sync=False):
        """Return a lightweight, paginated list of customers for offline
        caching in the POS frontend.

        Only id/name/phone/mobile are returned (never full partner data)
        to keep payloads small enough for very large customer databases.

        :param offset: pagination offset, used by the JS side to fetch
            the full customer base in chunks on first sync.
        :param limit: max number of records per call.
        :param last_sync: ISO datetime string. When provided, only
            records written after this time are returned (incremental
            sync), so subsequent session opens only fetch deltas instead
            of the whole customer base again.
        :return: dict with 'partners' (list of dicts) and 'server_time'
            (the server's current time, to be stored by the client as the
            new last_sync value).
        """
        domain = []
        if last_sync:
            domain = [('write_date', '>', last_sync)]

        partners = self.search_read(
            domain,
            ['id', 'name', 'phone', 'mobile'],
            offset=offset,
            limit=limit,
            order='id',
        )
        return {
            'partners': partners,
            'server_time': fields.Datetime.to_string(fields.Datetime.now()),
        }
