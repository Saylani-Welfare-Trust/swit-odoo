from odoo import models, fields, api, _
from odoo.exceptions import UserError

class MicrofinanceApplicationWizard(models.TransientModel):
    _name = 'microfinance.application.wizard'
    _description = 'Microfinance Application Wizard'


    partner_ids = fields.Many2many('res.partner', string="Partner", required=True)
    microfinance_scheme_id = fields.Many2one('microfinance.scheme', string="Microfinance Scheme", required=True)


    def action_print_application(self):
        """Create separate microfinance records for each selected partner"""
        self.ensure_one()
        
        if not self.partner_ids:
            raise UserError(_("Please select at least one partner."))
        
        created_records = self.env['microfinance']
        errors = []
        
        # Process each partner individually
        for partner in self.partner_ids:
            # Check if this partner is already enrolled
            existing = self.env['microfinance'].search([
                ('donee_id', '=', partner.id),
                ('microfinance_scheme_id', '=', self.microfinance_scheme_id.id),
                ('state', '!=', 'rejected'),
                ('in_recovery', '=', False),
            ], limit=1)

            if existing:
                errors.append(_("Partner %s is already enrolled in this scheme.") % partner.name)
                continue

            # Create microfinance record for this partner
            microfinance = self.env['microfinance'].create({
                'microfinance_scheme_id': self.microfinance_scheme_id.id,
                'donee_id': partner.id,  # ✅ Single integer
            })
            
            # Compute the scheme lines
            microfinance._compute_microfinance_scheme_line_ids()
            created_records |= microfinance
        
        # Handle errors
        if errors and not created_records:
            raise UserError(_("No applications could be created.\n\n%s") % "\n".join(errors))
        
        if not created_records:
            raise UserError(_("No applications were created."))
        
        # If multiple records created, show them in a list view
        if len(created_records) > 1:
            # Show a warning with success message
            warning_msg = _("Successfully created %d applications.") % len(created_records)
            if errors:
                warning_msg += _("\n\nHowever, the following could not be created:\n%s") % "\n".join(errors)
            
            return {
                'type': 'ir.actions.act_window',
                'name': _('Microfinance Applications Created'),
                'res_model': 'microfinance',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', created_records.ids)],
                'target': 'current',
                'context': {
                    'default_state': 'draft',
                }
            }
        
        # If only one record, print it directly
        return self.env.ref('bn_profile_management.action_report_microfinance_application_form').report_action(
            created_records.donee_id
        )