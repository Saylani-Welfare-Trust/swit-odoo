STALE_VIEWS = (
    'pos_config_view_form_inherit_bn_medical_prescription',
    'mh_pos_config_view_kanban_inherit_prescription',
)


def migrate(cr, version):
    """The counters have a single type now: drop the views on the removed medical_pos_role field
    before the registry validates the views of pos.config against the new model."""
    cr.execute("""
        DELETE FROM ir_ui_view
         WHERE id IN (SELECT res_id FROM ir_model_data
                       WHERE module = 'bn_medical_prescription' AND model = 'ir.ui.view' AND name IN %s)
    """, [STALE_VIEWS])
    cr.execute("""
        DELETE FROM ir_model_data
         WHERE module = 'bn_medical_prescription' AND model = 'ir.ui.view' AND name IN %s
    """, [STALE_VIEWS])
