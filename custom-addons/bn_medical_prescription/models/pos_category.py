from odoo import api, fields, models


class PosCategory(models.Model):
    _inherit = 'pos.category'

    mh_prescription = fields.Boolean(
        string="Prescription",
        help="The products of this category (and of its sub-categories) can be added to the product lines "
             "of a prescription.",
    )
    # switched on, or under a category switched on: what the prescription lines offer
    mh_prescription_scope = fields.Boolean(
        string="In Prescriptions", compute='_compute_mh_prescription_scope', store=True, recursive=True, index=True)

    @api.depends('mh_prescription', 'parent_id.mh_prescription_scope')
    def _compute_mh_prescription_scope(self):
        for category in self:
            category.mh_prescription_scope = category.mh_prescription or category.parent_id.mh_prescription_scope
