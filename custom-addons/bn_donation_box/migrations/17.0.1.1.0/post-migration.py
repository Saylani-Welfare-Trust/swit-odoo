# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # 1. The historical global "Donation Box" operation type has no warehouse, so the
    #    warehouse record rules of bn_stock_location hide it from restricted users.
    #    Bind it to the warehouse it serves and make it that warehouse's default.
    env['stock.warehouse']._bn_migrate_legacy_donation_box_type()
    env.flush_all()

    # 2. Back-fill the new warehouse / company columns of existing requests.
    cr.execute("""
        UPDATE donation_box_request r
           SET warehouse_id = pt.warehouse_id
          FROM stock_picking_type pt
         WHERE r.picking_type_id = pt.id
           AND r.warehouse_id IS NULL
           AND pt.warehouse_id IS NOT NULL
    """)
    cr.execute("""
        UPDATE donation_box_request r
           SET company_id = COALESCE(pt.company_id, (SELECT id FROM res_company ORDER BY id LIMIT 1))
          FROM stock_picking_type pt
         WHERE r.picking_type_id = pt.id
           AND r.company_id IS NULL
    """)
    cr.execute("""
        UPDATE donation_box_request
           SET company_id = (SELECT id FROM res_company ORDER BY id LIMIT 1)
         WHERE company_id IS NULL
    """)
    _logger.info("bn_donation_box 17.0.1.1.0: operation types bound to warehouses, requests back-filled.")
