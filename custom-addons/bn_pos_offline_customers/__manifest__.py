{
    'name': 'POS Offline Customers',
    'version': '17.0.1.0.0',
    'category': 'Point of Sale',
    'summary': 'Preload and search customers offline in Point of Sale',
    'description': """
POS Offline Customers
======================

Preloads a lightweight customer list (id, name, phone, mobile) into the
browser's IndexedDB when a POS session opens, and keeps it in sync
incrementally (only new/changed customers are re-fetched after the first
full sync).

This lets the POS search customers by name or phone even when the
internet connection drops, without downloading full partner records for
every customer (address, notes, tags, etc.), which would be far too much
data for large customer databases.

Designed for shops with very large customer counts (100k+) where the
default full partner preload is not practical.
""",
    'author': 'Abdul Hai',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/POS',
    'depends': ['point_of_sale'],
    'data': [],
    'assets': {
        'point_of_sale.assets': [
            'bn_pos_offline_customers/static/src/js/customer_offline_db.js',
            'bn_pos_offline_customers/static/src/js/pos_store_patch.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
