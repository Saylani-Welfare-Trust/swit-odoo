from odoo import models, fields, api


class MicrofinanceApplicationWizard(models.TransientModel):
    _name = 'microfinance.application.wizard'
    _description = 'Microfinance Application Wizard'

    partner_id = fields.Many2one('res.partner', string="Partner", required=True)
    microfinance_scheme_id = fields.Many2one('microfinance.scheme', string="Microfinance Scheme", required=True)

    def action_print_application(self):
        """Create microfinance record and print the application form"""
        self.ensure_one()
        
        # Create microfinance record with the selected scheme
        microfinance = self.env['microfinance'].create({
            'microfinance_scheme_id': self.microfinance_scheme_id.id,
            'donee_id': self.partner_id.id
        })

        # Compute the scheme lines
        microfinance._compute_microfinance_scheme_line_ids()

        # Return the report action
        return self.env.ref('bn_profile_management.action_report_microfinance_application_form').report_action(self.partner_id)
