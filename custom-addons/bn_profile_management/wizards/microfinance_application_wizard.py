from odoo import models, fields, api, _
from odoo.exceptions import UserError

class MicrofinanceApplicationWizard(models.TransientModel):
    _name = 'microfinance.application.wizard'
    _description = 'Microfinance Application Wizard'


    partner_ids = fields.Many2many('res.partner', string="Partner", required=True)
    microfinance_scheme_id = fields.Many2one('microfinance.scheme', string="Microfinance Scheme", required=True)


    def action_print_application(self):
        """Create a single microfinance record with all selected partners"""
        self.ensure_one()
        
        if not self.partner_ids:
            raise UserError(_("Please select at least one partner."))
        
        # Check if any selected partner is already enrolled
        existing = self.env['microfinance'].search([
            ('donee_ids', 'in', self.partner_ids.ids),  # Check Many2many field
            ('microfinance_scheme_id', '=', self.microfinance_scheme_id.id),
            ('state', '!=', 'rejected'),
            ('in_recovery', '=', False),
        ])
        
        # Find which partners are already enrolled
        enrolled_partners = existing.mapped('donee_ids')
        already_enrolled = self.partner_ids & enrolled_partners
        
        if already_enrolled:
            partner_names = ', '.join(already_enrolled.mapped('name'))
            raise UserError(_(
                "The following donees are already enrolled in the selected scheme:\n\n"
                "%s\n\n"
                "Please remove them from the list or select a different scheme."
            ) % partner_names)

        # Create a single microfinance record with all selected partners
        microfinance = self.env['microfinance'].create({
            'microfinance_scheme_id': self.microfinance_scheme_id.id,
            'donee_ids': [(6, 0, self.partner_ids.ids)],  # ✅ Many2many format
        })

        # Compute the scheme lines
        microfinance._compute_microfinance_scheme_line_ids()

        # Return the report action for all partners
        return self.env.ref('bn_profile_management.action_report_microfinance_application_form').report_action(self.partner_ids)