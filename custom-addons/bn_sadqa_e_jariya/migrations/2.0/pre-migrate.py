# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    2.0: Sadqa e Jariya has its own models instead of extending welfare (only test data existed,
    nothing is moved). The old models, the fields added to welfare and their actions are removed
    at the end of the upgrade; here, before the new data is loaded:
    - the old views on welfare models are deleted, so updating a welfare view in the same upgrade
      doesn't validate them against fields that are gone
    - welfare records left in Form Sent / Form Filled go back to Completed
    - the INS/<year>/xxxx sequence is kept, numbering goes on
    """
    cr.execute("""
        DELETE FROM ir_ui_view v
         USING ir_model_data d
         WHERE d.module = 'bn_sadqa_e_jariya' AND d.model = 'ir.ui.view' AND d.res_id = v.id
           AND v.model LIKE 'welfare%'
    """)
    _logger.info("bn_sadqa_e_jariya: %s old welfare views removed", cr.rowcount)
    cr.execute("""
        DELETE FROM ir_model_data d
         WHERE d.module = 'bn_sadqa_e_jariya' AND d.model = 'ir.ui.view'
           AND NOT EXISTS (SELECT 1 FROM ir_ui_view v WHERE v.id = d.res_id)
    """)

    cr.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'welfare'")
    if cr.fetchone():
        cr.execute("UPDATE welfare SET state = 'completed' WHERE state IN ('form_sent', 'form_filled')")
        _logger.info("bn_sadqa_e_jariya: %s welfare records back to Completed", cr.rowcount)

    cr.execute("""
        UPDATE ir_model_data SET name = 'sadqa_jariya_sequence'
         WHERE module = 'bn_sadqa_e_jariya' AND name = 'welfare_institution_sequence'
    """)
    cr.execute("UPDATE ir_sequence SET code = 'sadqa.jariya' WHERE code = 'welfare_institution_sequence'")
