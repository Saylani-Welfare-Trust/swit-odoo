{
    "name": "POS Bulk Customer Sync (500K+ customers, offline)",
    "version": "17.0.1.0.0",
    "category": "Point of Sale",
    "summary": "Sync very large customer databases to POS terminals for offline use, "
                "via slim payloads + chunked background loading + phone-indexed local search.",
    "description": """
Why this module exists
=======================
Stock Odoo POS loads the full res.partner record for every customer into an
in-memory JS array and searches it with a linear scan. That's fine for a few
hundred/thousand customers. It falls over hard well before 100K, and is not
viable at 500K across many terminals.

This module changes two things:

1. Stops the default POS partner loader from pulling res.partner at all
   (see models/pos_session.py). Instead the POS frontend pulls a *slim*
   dataset (id, name, phone, mobile, barcode, pricelist_id) through a
   dedicated paginated controller (controllers/main.py), in chunks, in the
   background, after the session is already usable.

2. Stores that slim dataset in IndexedDB with an index on phone/mobile, and
   patches the customer search to query that index directly instead of
   filtering a giant JS array (static/src/js/*).

What you still need to do
==========================
- Adjust the exact JS patch targets to match your installed 17.0.x point of
  sale module structure (Odoo has changed internal file layout between minor
  releases; the touch points here are the *documented public entry points*:
  the models loader and the customer screen search, but confirm the class/
  file names against your addons/point_of_sale source before deploying).
- Load-test against your real server (25 concurrent tills doing the initial
  bulk pull will hit Postgres hard - see the nightly snapshot cron in
  data/ir_cron.xml, which pre-generates the payload so tills fetch a static
  file instead of triggering 25 live ORM searches over 500K rows).
- Confirm target till hardware has enough browser storage headroom (~100-300MB
  depending on browser/OS storage quota policy).
""",
    "depends": ["point_of_sale"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "bn_pos_bulk_customer_sync/static/src/js/customer_indexeddb.js",
            "bn_pos_bulk_customer_sync/static/src/js/customer_sync.js",
            "bn_pos_bulk_customer_sync/static/src/js/customer_search_patch.js",
        ],
    },
    "installable": True,
    "license": "LGPL-3",
}
