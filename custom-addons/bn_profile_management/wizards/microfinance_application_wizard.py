from odoo import models, fields, api, _
from odoo.exceptions import UserError

class MicrofinanceApplicationWizard(models.TransientModel):
    _name = 'microfinance.application.wizard'
    _description = 'Microfinance Application Wizard'


    partner_ids = fields.Many2many('res.partner', string="Partner", required=True)
    microfinance_scheme_id = fields.Many2one('microfinance.scheme', string="Microfinance Scheme", required=True)


    def action_print_application(self):
        """Create microfinance applications for selected partners"""
        self.ensure_one()
        
        if not self.partner_ids:
            raise UserError(_("Please select at least one partner."))
        
        # If only ONE partner is selected → Print the application
        if len(self.partner_ids) == 1:
            partner = self.partner_ids[0]
            
            # Check if already enrolled
            existing = self.env['microfinance'].search([
                ('donee_id', '=', partner.id),
                ('microfinance_scheme_id', '=', self.microfinance_scheme_id.id),
                ('state', '!=', 'rejected'),
                ('in_recovery', '=', False),
            ], limit=1)

            if existing:
                raise UserError(_(
                    "This donee is already enrolled in the selected scheme.\n\n"
                    "They may enroll in a different scheme, or re-apply only if the previous request was rejected or in a recovery phase."
                ))

            # Create microfinance record
            microfinance = self.env['microfinance'].create({
                'microfinance_scheme_id': self.microfinance_scheme_id.id,
                'donee_id': partner.id,
            })

            # Compute scheme lines
            microfinance._compute_microfinance_scheme_line_ids()

            # Register the partner
            partner.action_register()

            # ✅ PRINT the application form
            return self.env.ref('bn_profile_management.action_report_microfinance_application_form').report_action(partner)
        
        # If MULTIPLE partners are selected → Create applications WITHOUT printing
        else:
            created_records = self.env['microfinance']
            registered_partners = self.env['res.partner']
            errors = []
            
            for partner in self.partner_ids:
                # Check if already enrolled
                existing = self.env['microfinance'].search([
                    ('donee_id', '=', partner.id),
                    ('microfinance_scheme_id', '=', self.microfinance_scheme_id.id),
                    ('state', '!=', 'rejected'),
                    ('in_recovery', '=', False),
                ], limit=1)

                if existing:
                    errors.append(_("Partner '%s' is already enrolled.") % partner.name)
                    continue

                try:
                    # Create microfinance record
                    microfinance = self.env['microfinance'].create({
                        'microfinance_scheme_id': self.microfinance_scheme_id.id,
                        'donee_id': partner.id,
                    })
                    
                    # Compute scheme lines
                    microfinance._compute_microfinance_scheme_line_ids()
                    created_records |= microfinance
                    
                    # Register the partner
                    partner.action_register()
                    registered_partners |= partner
                    
                except Exception as e:
                    errors.append(_("Partner '%s': %s") % (partner.name, str(e)))
            
            # Handle errors
            if errors and not created_records:
                raise UserError(_("No applications could be created.\n\n%s") % "\n".join(errors))
            
            if not created_records:
                raise UserError(_("No applications were created."))
            
            # Show success message
            success_msg = _(
                "✅ %d application(s) created successfully!\n"
                "✅ %d partner(s) registered successfully!"
            ) % (len(created_records), len(registered_partners))
            
            if errors:
                success_msg += _("\n\n⚠️ Issues:\n%s") % "\n".join(errors)
            
            # Return to list view of created applications (NO PRINT)
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