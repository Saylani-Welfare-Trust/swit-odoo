from odoo import models, fields, api, _
from odoo.exceptions import UserError

class MicrofinanceApplicationWizard(models.TransientModel):
    _name = 'microfinance.application.wizard'
    _description = 'Microfinance Application Wizard'


    partner_id = fields.Many2one('res.partner', string="Partner", required=True)
    microfinance_scheme_id = fields.Many2one('microfinance.scheme', string="Microfinance Scheme", required=True)


    def action_print_application(self):
        """Create microfinance record and print the application form"""
        self.ensure_one()
        # Profile staff start the application: the loan record is created as
        # superuser once the user is checked (Profile Management or Microfinance user).
        user = self.env.user
        if not self.env.su and not (user.has_group('bn_profile_management.profile_management_user_group')
                                    or user.has_group('bn_microfinance.microfinance_user_group')):
            raise UserError(_('You are not allowed to start a Microfinance application.'))

        # Check existing enrollment
        existing = self.env['microfinance'].sudo().search([
            ('donee_id', '=', self.partner_id.id),
            ('microfinance_scheme_id', '=', self.microfinance_scheme_id.id),
            ('state', '!=', 'reject'),
            ('in_recovery', '=', False),

        ], limit=1)

        if existing:
            raise UserError(_(
                "This donee is already enrolled in the selected scheme.\n\n"
                "They may enroll in a different scheme, or re-apply only if the previous request was rejected or in a recovery phase."
            ))

        # Create microfinance record
        microfinance = self.env['microfinance'].sudo().create({
            'microfinance_scheme_id': self.microfinance_scheme_id.id,
            'donee_id': self.partner_id.id,
        })

        # Compute the scheme lines
        microfinance._compute_microfinance_scheme_line_ids()

        # Return the report action
        return self.env.ref('bn_microfinance.action_report_microfinance_application_form').report_action(self.partner_id)
