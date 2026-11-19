from odoo import api, models

DONOR_ACCOUNT_CODE = 'donor_account'


class ResPartnerCategory(models.Model):
    _inherit = 'res.partner.category'

    @api.model
    def _setup_donor_account_program(self):
        """Run on every install / upgrade: the "Donor Account" tag is the
        programme of the Advance Donation Record Search (donor side). A tag
        of that name made by hand is reused; an administrator's later changes
        to the tag are kept."""
        if self._record_search_program(DONOR_ACCOUNT_CODE):
            return
        Category = self.sudo()
        tag = Category.search([('name', '=ilike', 'Donor Account'),
                               ('registration_program_code', '=', False)], limit=1)
        vals = {'registration_program_code': DONOR_ACCOUNT_CODE, 'registration_role': 'donor'}
        if tag:
            tag.write(vals)
        else:
            Category.create(dict(vals, name='Donor Account'))
