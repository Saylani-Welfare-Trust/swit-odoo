from odoo import models, api, fields
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'


    categories = fields.Char('Categories', compute="_compute_category_names", store=True)


    @api.depends('category_id')
    def _compute_category_names(self):
        for partner in self:
            partner.categories = ""

            if partner.category_id:
                partner.categories = ", ".join(partner.category_id.mapped("name"))

    @api.model
    def create_from_ui(self, partner):
        # raise ValidationError(str(partner))
        
        if partner.get('country_code_id'):
            country_id = self.env['res.country'].search([('id', '=', int(partner.get('country_code_id')))], limit=1).id
            partner['country_id'] = country_id

        partner['cnic_no'] = partner.get('cnic_no')

        partner['category_id'] = [(6, 0, [
            self.env.ref('bn_profile_management.donor_partner_category').id,
            self.env.ref('bn_profile_management.individual_partner_category').id 
            if partner.get('donor_type') == 'individual' 
            else self.env.ref('bn_profile_management.coorporate_institute_partner_category').id
        ])]

        partner.pop('donor_type', None)

        return super(ResPartner, self).create_from_ui(partner)
