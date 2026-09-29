from odoo import models, api, fields
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'


    categories = fields.Char('Categories', compute="_compute_category_names", store=True, tracking=True)


    @api.depends('category_id')
    def _compute_category_names(self):
        for partner in self:
            partner.categories = ""

            if partner.category_id:
                partner.categories = ", ".join(partner.category_id.mapped("name"))

    @api.model
    def create_from_ui(self, partner):
        if partner.get('country_code_id'):
            country_id = self.env['res.country'].search([('id', '=', int(partner.get('country_code_id')))], limit=1).id
            partner['country_id'] = country_id

        # NOTE: bn_profile_management already depends on bn_pos_customization, so this
        # module cannot declare a dependency back on it (that would be circular). The
        # categories below are only assigned if bn_profile_management happens to be
        # installed; look them up defensively instead of a hard env.ref().
        category_ids = []
        donor_category = self.env.ref('bn_profile_management.donor_partner_category', raise_if_not_found=False)
        if donor_category:
            category_ids.append(donor_category.id)
            individual_category = self.env.ref('bn_profile_management.individual_partner_category', raise_if_not_found=False)
            corporate_category = self.env.ref('bn_profile_management.coorporate_institute_partner_category', raise_if_not_found=False)
            extra_category = individual_category if partner.get('donor_type') == 'individual' else corporate_category
            if extra_category:
                category_ids.append(extra_category.id)
        if category_ids:
            partner['category_id'] = [(6, 0, category_ids)]

        partner.pop('donor_type', None)

        return super(ResPartner, self).create_from_ui(partner)
