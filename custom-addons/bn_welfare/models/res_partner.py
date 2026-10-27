from odoo import models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _profile_welfare_installed(self):
        return True

    def action_welfare_application(self):
        """Create the Welfare application of a newly registered welfare donee."""
        self.ensure_one()
        Welfare = self.env['welfare']
        existing = Welfare.search([('donee_id', '=', self.id)], limit=1)
        if existing:
            return existing
        return Welfare.create({
            'donee_id': self.id,
            'is_individual': 'Individual' in self.category_id.mapped('name'),
        })
