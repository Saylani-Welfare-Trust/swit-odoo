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
        
        created_records = self.env['microfinance']
        errors = []
        successful_partners = self.env['res.partner']
        
        for partner in self.partner_ids:
            # Check if already enrolled in this scheme
            existing = self.env['microfinance'].search([
                ('donee_id', '=', partner.id),
                ('microfinance_scheme_id', '=', self.microfinance_scheme_id.id),
                ('state', '!=', 'rejected'),
                ('in_recovery', '=', False),
            ], limit=1)

            if existing:
                errors.append(_("Partner '%s' is already enrolled in this scheme.") % partner.name)
                continue

            try:
                # Create microfinance record
                microfinance = self.env['microfinance'].create({
                    'microfinance_scheme_id': self.microfinance_scheme_id.id,
                    'donee_id': partner.id,
                })
                microfinance._compute_microfinance_scheme_line_ids()
                created_records |= microfinance
                
                # Register the partner
                partner.action_register()
                successful_partners |= partner
                
            except ValidationError as e:
                errors.append(_("Partner '%s': %s") % (partner.name, str(e)))
                # Clean up if creation failed
                if microfinance:
                    microfinance.unlink()
            except Exception as e:
                errors.append(_("Partner '%s': %s") % (partner.name, str(e)))
                if microfinance:
                    microfinance.unlink()
        
        if not created_records:
            raise UserError(_("No applications could be created.\n\n%s") % "\n".join(errors))
        
        # Single partner → Print
        if len(self.partner_ids) == 1:
            return self.env.ref('bn_profile_management.action_report_microfinance_application_form').report_action(
                created_records.donee_id
            )
        
        # Multiple partners → Show list (NO PRINT)
        else:
            message = _("✅ %d application(s) created successfully!") % len(created_records)
            message += _("\n✅ %d partner(s) registered successfully!") % len(successful_partners)
            if errors:
                message += _("\n\n⚠️ Issues:\n%s") % "\n".join(errors)
            
            return {
                'type': 'ir.actions.act_window',
                'name': _('Microfinance Applications Created'),
                'res_model': 'microfinance',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', created_records.ids)],
                'target': 'current',
            }