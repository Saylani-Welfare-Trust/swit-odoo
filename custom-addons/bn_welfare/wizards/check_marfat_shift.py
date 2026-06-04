from odoo import models, fields, api
from odoo.exceptions import UserError


class WelfareLineDisbursementPopup(models.TransientModel):
    _name = 'welfare.line.disbursement.popup'
    _description = 'Welfare Line Disbursement Popup'

    line_id = fields.Many2one('welfare.line', string='Disbursement Line', required=True)
    welfare_id = fields.Many2one('welfare', related='line_id.welfare_id', readonly=True)
    donee_id = fields.Many2one('res.partner', related='line_id.welfare_id.donee_id', readonly=True)
    donee_cnic_no = fields.Char(string='CNIC', related='line_id.welfare_id.donee_id.cnic_no', readonly=True)
    donee_mobile = fields.Char(string='Mobile', related='line_id.welfare_id.donee_id.mobile', readonly=True)
    donee_street = fields.Char(string='Street', related='line_id.welfare_id.donee_id.street', readonly=True)
    donee_street2 = fields.Char(string='Street 2', related='line_id.welfare_id.donee_id.street2', readonly=True)
    donee_city = fields.Char(string='City', related='line_id.welfare_id.donee_id.city', readonly=True)
    donee_state_id = fields.Many2one('res.country.state', string='State', related='line_id.welfare_id.donee_id.state_id', readonly=True)
    donee_country_id = fields.Many2one('res.country', string='Country', related='line_id.welfare_id.donee_id.country_id', readonly=True)

    disbursement_category_id = fields.Many2one('disbursement.category', related='line_id.disbursement_category_id', readonly=True)
    disbursement_application_type_id = fields.Many2one('disbursement.application.type', related='line_id.disbursement_application_type_id', readonly=True)
    product_id = fields.Many2one('product.product', related='line_id.product_id', readonly=True)
    quantity = fields.Float(related='line_id.quantity', readonly=True)
    total_amount = fields.Float(related='line_id.total_amount', readonly=True)
    collection_point = fields.Selection(related='line_id.collection_point', readonly=True)
    collection_date = fields.Date(related='line_id.collection_date', readonly=True)
    assigned_officer_id = fields.Many2one('hr.employee', related='line_id.assigned_officer_id', readonly=True)
    state = fields.Selection(related='line_id.state', readonly=True)

    def action_mark_pending(self):
        # Create return line
        self.env['welfare.return.line'].create({
            'welfare_line_id': self.line_id.id,
            'welfare_id': self.line_id.welfare_id.id,
            'donee_id': self.line_id.welfare_id.donee_id.id,
            'product_id': self.line_id.product_id.id,
            'quantity': self.line_id.quantity,
            'total_amount': self.line_id.total_amount,
            'return_date': fields.Date.today(),
            'state': 'pending',
        })

        # Create new welfare + copy all form data + copy line
        # Pass create_return_line=False to avoid creating return line twice
        self.line_id.action_set_pending(create_return_line=False)

        return {
            'type': 'ir.actions.client',
            'tag': 'reload'
        }
    def action_disbursed(self):
        self.welfare_id._auto_disburse_if_all_lines_delivered()
        self.line_id.write({'state': 'disbursed'})

        return {'type': 'ir.actions.client', 'tag': 'reload'}


class WelfareRecurringLineDisbursementPopup(models.TransientModel):
    _name = 'welfare.recurring.line.disbursement.popup'
    _description = 'Welfare Recurring Line Disbursement Popup'

    recurring_line_id = fields.Many2one('welfare.recurring.line', string='Recurring Line', required=True)
    welfare_id = fields.Many2one('welfare', related='recurring_line_id.welfare_id', readonly=True)
    donee_id = fields.Many2one('res.partner', related='recurring_line_id.welfare_id.donee_id', readonly=True)
    donee_cnic_no = fields.Char(string='CNIC', related='recurring_line_id.welfare_id.donee_id.cnic_no', readonly=True)
    donee_mobile = fields.Char(string='Mobile', related='recurring_line_id.welfare_id.donee_id.mobile', readonly=True)
    donee_street = fields.Char(string='Street', related='recurring_line_id.welfare_id.donee_id.street', readonly=True)
    donee_street2 = fields.Char(string='Street 2', related='recurring_line_id.welfare_id.donee_id.street2', readonly=True)
    donee_city = fields.Char(string='City', related='recurring_line_id.welfare_id.donee_id.city', readonly=True)
    donee_state_id = fields.Many2one('res.country.state', string='State', related='recurring_line_id.welfare_id.donee_id.state_id', readonly=True)
    donee_country_id = fields.Many2one('res.country', string='Country', related='recurring_line_id.welfare_id.donee_id.country_id', readonly=True)

    disbursement_category_id = fields.Many2one('disbursement.category', related='recurring_line_id.disbursement_category_id', readonly=True)
    disbursement_application_type_id = fields.Many2one('disbursement.application.type', related='recurring_line_id.disbursement_application_type_id', readonly=True)
    product_id = fields.Many2one('product.product', related='recurring_line_id.product_id', readonly=True)
    currency_id = fields.Many2one('res.currency', related='recurring_line_id.currency_id', readonly=True)
    quantity = fields.Float(related='recurring_line_id.quantity', readonly=True)
    amount = fields.Monetary(related='recurring_line_id.amount', readonly=True, currency_field='currency_id')
    collection_point = fields.Selection(related='recurring_line_id.collection_point', readonly=True)
    collection_date = fields.Date(related='recurring_line_id.collection_date', readonly=True)
    assigned_officer_id = fields.Many2one('hr.employee', related='recurring_line_id.assigned_officer_id', readonly=True)
    state = fields.Selection(related='recurring_line_id.state', readonly=True)

    def action_disbursed(self):
        self.recurring_line_id.action_disbursed()
        return {'type': 'ir.actions.client', 'tag': 'reload'}


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
        compute='_compute_assigned_officers',
        store=True
    )

    # Display fields for the results
    disbursement_line_ids = fields.Many2many(
        'welfare.line',
        string="Disbursement Lines",
        readonly=True,
        compute='_compute_disbursement_lines'
    )

    recurring_line_ids = fields.Many2many(
        'welfare.recurring.line',
        string="Recurring Lines",
        readonly=True,
        compute='_compute_recurring_lines'
    )
    
    @api.depends('employee_category_id_officer')
    def _compute_assigned_officers(self):
        """
        Assign only the currently logged-in employee
        if that employee belongs to the selected category.
        """

        current_employee = self.env['hr.employee'].search([
            ('user_id', '=', self.env.user.id)
        ], limit=1)

        for rec in self:
            rec.assigned_officer_id = False

            if current_employee:
                    rec.assigned_officer_id = current_employee.id

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
                    ('collection_date', '=', today),
                    ('state','not in', ['disbursed'])
                ])

                rec.disbursement_line_ids = welfare_lines
            else:
                rec.disbursement_line_ids = False

    @api.depends('assigned_officer_id')
    def _compute_recurring_lines(self):
        """
        Fetch all recurring lines for the selected assigned officer with today's collection date.
        """
        for rec in self:
            if rec.assigned_officer_id:
                today = fields.Date.today()
                recurring_lines = self.env['welfare.recurring.line'].search([
                    ('assigned_officer_id', '=', rec.assigned_officer_id.id),
                    ('collection_date', '=', today),
                    ('state', 'not in', ['disbursed'])
                ])

                rec.recurring_line_ids = recurring_lines
            else:
                rec.recurring_line_ids = False

    def action_check_shift(self):
        """
        Check shift button action - triggers recomputation of disbursement lines
        """
        if not self.assigned_officer_id:
            raise UserError("Please select an Assigned Officer (Marfat)")

        # Trigger recompute of disbursement_line_ids
        self._compute_disbursement_lines()
        self._compute_recurring_lines()

        # Return action to refresh the view
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def mark_selected_as_collected(self):
        """Mark all selected disbursement lines as collected"""
        for line in self.disbursement_line_ids:
            if line.state != 'collected':
                line.write({'state': 'collected'})
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
