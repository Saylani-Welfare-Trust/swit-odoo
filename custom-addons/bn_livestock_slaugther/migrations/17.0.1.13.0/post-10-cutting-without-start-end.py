def migrate(cr, version):
    """Cutting has no Start / End steps any more: a material request is done once
    its materials are sent, and its animal with it."""
    if not version:
        return
    cr.execute("UPDATE livestock_cutting_material SET state = 'done' WHERE materials_sent AND state != 'done'")
    cr.execute("""
        UPDATE livestock_slaugther s SET state = 'done'
          FROM livestock_cutting_material m
         WHERE m.id = s.material_request_id AND m.materials_sent
           AND s.state IN ('cutting', 'material_request')
    """)
