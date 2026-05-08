from odoo import models, fields, api
from odoo.exceptions import UserError


class CheckMarfatShift(models.TransientModel):
    _name = 'check.marfat.shift'
    _description = 'Check Assigned Officer (Marfat) Shift Disbursements'

    assigned_officer_id = fields.Many2one(
        'hr.employee',
        string="Assigned Officer (Marfat)",
        domain="[('is_welfare_marfat', '=', True)]",
        required=True
    )
    
    # Display fields for the results
    disbursement_line_ids = fields.Many2many(
        'welfare.line',
        string="Disbursement Lines",
        readonly=True,
        compute='_compute_disbursement_lines'
    )

    @api.depends('assigned_officer_id')
    def _compute_disbursement_lines(self):
        """
        Fetch all disbursement lines for the selected assigned officer
        """
        for rec in self:
            if rec.assigned_officer_id:
                # Find all welfare lines assigned to this officer
                welfare_lines = self.env['welfare.line'].search([
                    ('assigned_officer_id', '=', rec.assigned_officer_id.id),
                ])
                
                rec.disbursement_line_ids = welfare_lines
            else:
                rec.disbursement_line_ids = False

    def action_check_shift(self):
        """
        Check shift button action - triggers recomputation of disbursement lines
        """
        if not self.assigned_officer_id:
            raise UserError("Please select an Assigned Officer (Marfat)")
        
        # Trigger recompute of disbursement_line_ids
        self._compute_disbursement_lines()
        
        # Return action to refresh the view
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
