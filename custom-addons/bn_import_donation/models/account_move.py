from odoo import models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    # The donations of the import are posted by its Confirm (with this entry)
    import_donation_id = fields.Many2one('import.donation', string="Import Donation", copy=False, index='btree_not_null')
