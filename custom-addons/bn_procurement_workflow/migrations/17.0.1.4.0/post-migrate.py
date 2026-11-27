import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _column(cr, table, column):
    cr.execute("SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
               (table, column))
    return bool(cr.fetchone())


def migrate(cr, version):
    """Assigned To (assigned_employee_id) became a many2many (assigned_employee_ids):
    each Purchase Request keeps the employee it was assigned to. The old columns
    are dropped by Odoo once the module is loaded, with their removed fields."""
    if not _column(cr, 'purchase_requisition', 'assigned_employee_id'):
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    # the new fields' computations pending from their creation run first, so
    # that they don't overwrite what is inserted below
    env.flush_all()
    cr.execute("""
        INSERT INTO purchase_requisition_assigned_employee_rel (requisition_id, employee_id)
        SELECT id, assigned_employee_id
          FROM purchase_requisition
         WHERE assigned_employee_id IS NOT NULL
        ON CONFLICT DO NOTHING
    """)
    _logger.info("Purchase Requests: %s assignments moved to Assigned To (many2many)", cr.rowcount)
    cr.execute("""
        INSERT INTO purchase_requisition_assigned_user_rel (requisition_id, user_id)
        SELECT pr.id, emp.user_id
          FROM purchase_requisition pr
          JOIN hr_employee emp ON emp.id = pr.assigned_employee_id
         WHERE emp.user_id IS NOT NULL
        ON CONFLICT DO NOTHING
    """)
    env.invalidate_all()
