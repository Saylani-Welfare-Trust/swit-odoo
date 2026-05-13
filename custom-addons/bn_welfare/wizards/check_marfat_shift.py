from odoo import models, fields, api
from odoo.exceptions import UserError


class CheckMarfatShift(models.TransientModel):
    _name = 'check.marfat.shift'
    _description = 'Check Assigned Officer (Marfat) Shift Disbursements'

    employee_category_id_officer = fields.Many2one(
        'hr.employee.category',
        string="Employee Category",
        default=lambda self: self.env.ref('bn_welfare.assigned_officer_hr_employee_category', raise_if_not_found=False).id
    )

    assigned_officer_id = fields.Many2one(
        'hr.employee',
        string="Assigned Officer (Marfat)",
        domain="[('category_ids', 'in', [employee_category_id_officer])]",
        required=True
    )
    
    # New fields for officer information
    officer_name = fields.Char(
        string="Officer Name",
        compute='_compute_officer_info',
        store=False
    )
    
    officer_address = fields.Text(
        string="Address",
        compute='_compute_officer_info',
        store=False
    )

    # Display fields for the results
    disbursement_line_ids = fields.Many2many(
        'welfare.line',
        string="Disbursement Lines",
        readonly=False,  # Needed to allow editing state field
        compute='_compute_disbursement_lines',
        store=False
    )

    @api.depends('assigned_officer_id')
    def _compute_officer_info(self):
        """
        Fetch officer name and address from the selected employee
        """
        for rec in self:
            if rec.assigned_officer_id:
                rec.officer_name = rec.assigned_officer_id.name
                # Get address from related partner or employee fields
                if rec.assigned_officer_id.address_home_id:
                    rec.officer_address = rec.assigned_officer_id.address_home_id
                elif rec.assigned_officer_id.user_id and rec.assigned_officer_id.user_id.partner_id:
                    rec.officer_address = rec.assigned_officer_id.user_id.partner_id.contact_address
                elif rec.assigned_officer_id.parent_id and rec.assigned_officer_id.parent_id.address_home_id:
                    rec.officer_address = rec.assigned_officer_id.parent_id.address_home_id
                else:
                    rec.officer_address = "No address available"
            else:
                rec.officer_name = False
                rec.officer_address = False

    @api.depends('assigned_officer_id')
    def _compute_disbursement_lines(self):
        """
        Fetch all disbursement lines for the selected assigned officer with today's collection date
        """
        for rec in self:
            if rec.assigned_officer_id:
                today = fields.Date.today()
                # Find all welfare lines assigned to this officer with today's collection date
                welfare_lines = self.env['welfare.line'].search([
                    ('assigned_officer_id', '=', rec.assigned_officer_id.id),
                    ('collection_date', '=', today)
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

        # Trigger recompute of disbursement_lines and officer info
        self._compute_disbursement_lines()
        self._compute_officer_info()

        # Return action to refresh the view with editable mode
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'views': [(self.env.ref('bn_welfare.check_marfat_shift_form').id, 'form')],
        }
    
    def action_mark_as_collected(self):
        """
        Mark all disbursement lines as collected
        """
        if not self.disbursement_line_ids:
            raise UserError("No disbursement lines found to mark as collected")
        
        # Update all lines to 'collected' state
        self.disbursement_line_ids.write({'state': 'collected'})
        
        # Refresh the view to show updated states
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'edit': True},
        }