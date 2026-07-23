from odoo import models, fields, api, _
from odoo.exceptions import UserError

class MicrofinanceApplicationWizard(models.TransientModel):
    _name = 'microfinance.application.wizard'
    _description = 'Microfinance Application Wizard'


    partner_ids = fields.Many2many('res.partner', string="Partner", required=True)
    microfinance_scheme_id = fields.Many2one('microfinance.scheme', string="Microfinance Scheme", required=True)


    def action_print_application(self):
        self.ensure_one()
        
        if not self.partner_ids:
            raise UserError(_("Please select at least one partner."))
        
        primary_partner = self.partner_ids[0]
        additional_partners = self.partner_ids[1:]
        
        microfinance = self.env['microfinance'].create({
            'microfinance_scheme_id': self.microfinance_scheme_id.id,
            'donee_id': primary_partner.id,
            'additional_donee_ids': [(6, 0, additional_partners.ids)],
        })
        
        microfinance._compute_microfinance_scheme_line_ids()
        
        return self.env.ref('bn_profile_management.action_report_microfinance_application_form').report_action(self.partner_ids)