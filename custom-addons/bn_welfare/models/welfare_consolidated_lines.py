from odoo import api, fields, models

class WelfareConsolidatedLine(models.Model):
    _name = 'welfare.consolidated.line'
    _description = 'Consolidated Welfare Lines'
    _rec_name = 'display_name'
    _order = 'collection_date desc'
    
    # All fields from welfare.line
    employee_id = fields.Many2one('hr.employee', string='Employee')
    disbursement_category_id = fields.Many2one('disbursement.category', string='Category')
    disbursement_application_type_id = fields.Many2one('disbursement.application.type', string='Application Type')
    product_id = fields.Many2one('product.product', string='Product')
    payment_type = fields.Selection([
        ('self', 'Self'),
        ('officer', 'Officer'),
    ], string='Payment Type')
    assigned_officer_id = fields.Many2one('hr.employee', string='Assigned Officer')
    collection_point = fields.Selection([
        ('bank', 'Bank'),
        ('cash', 'Cash'),
    ], string='Collection Point')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    collection_date = fields.Date(string='Collection Date')
    marriage_date = fields.Date(string='Marriage Date')
    quantity = fields.Float(string='Quantity')
    amount = fields.Float(string='Amount')
    total_amount = fields.Float(string='Total Amount')
    advance_donation_amount = fields.Float(string='Advance Donation Amount')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('disbursed', 'Disbursed'),
        ('return', 'Return'),
        ('recurring', 'Recurring'),
    ], string='State')
    
    # Recurring specific fields
    is_recurring = fields.Boolean(string='Is Recurring')
    recurring_duration = fields.Integer(string='Recurring Duration')
    
    # Source tracking
    source_model = fields.Char(string='Source Model')
    source_id = fields.Integer(string='Source ID')
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=False)
    
    @api.depends('is_recurring', 'employee_id')
    def _compute_display_name(self):
        for record in self:
            prefix = "Recurring" if record.is_recurring else "Regular"
            name = record.employee_id.name if record.employee_id else "Unknown"
            record.display_name = f"{prefix} - {name}"
    
    @api.model
    def search(self, domain=None, offset=0, limit=None, order=None, count=False):
        """Simply get all records from both models"""
        if domain is None:
            domain = []
        
        # Get all welfare lines
        welfare_lines = self.env['welfare.line'].search(domain)
        recurring_lines = self.env['welfare.recurring.line'].search(domain)
        
        # Combine into consolidated records
        result = self
        for line in welfare_lines:
            # Create a new record in the consolidated model
            values = {
                'source_model': 'welfare.line',
                'source_id': line.id,
                'is_recurring': False,
                'employee_id': line.employee_id.id,
                'disbursement_category_id': line.disbursement_category_id.id,
                'disbursement_application_type_id': line.disbursement_application_type_id.id,
                'product_id': line.product_id.id,
                'payment_type': line.payment_type,
                'assigned_officer_id': line.assigned_officer_id.id,
                'collection_point': line.collection_point,
                'analytic_account_id': line.analytic_account_id.id,
                'collection_date': line.collection_date,
                'marriage_date': line.marriage_date,
                'quantity': line.quantity,
                'amount': line.amount,
                'total_amount': line.total_amount,
                'advance_donation_amount': line.advance_donation_amount,
                'state': line.state,
                'recurring_duration': 0,
            }
            result |= self.new(values)
        
        for line in recurring_lines:
            values = {
                'source_model': 'welfare.recurring.line',
                'source_id': line.id,
                'is_recurring': True,
                'employee_id': line.employee_id.id,
                'disbursement_category_id': line.disbursement_category_id.id,
                'disbursement_application_type_id': line.disbursement_application_type_id.id,
                'product_id': line.product_id.id,
                'payment_type': line.payment_type,
                'assigned_officer_id': line.assigned_officer_id.id,
                'collection_point': line.collection_point,
                'analytic_account_id': line.analytic_account_id.id,
                'collection_date': line.collection_date,
                'marriage_date': False,
                'quantity': line.quantity,
                'amount': line.amount,
                'total_amount': line.total_amount,
                'advance_donation_amount': 0.0,
                'state': line.state,
                'recurring_duration': line.recurring_duration,
            }
            result |= self.new(values)
        
        if count:
            return len(result)
        
        return result
    
    def action_open_source_record(self):
        """Open source record"""
        self.ensure_one()
        if self.source_model == 'welfare.line':
            return {
                'type': 'ir.actions.act_window',
                'name': 'Welfare Line',
                'res_model': 'welfare.line',
                'res_id': self.source_id,
                'view_mode': 'form',
                'target': 'current',
            }
        elif self.source_model == 'welfare.recurring.line':
            return {
                'type': 'ir.actions.act_window',
                'name': 'Recurring Welfare Line',
                'res_model': 'welfare.recurring.line',
                'res_id': self.source_id,
                'view_mode': 'form',
                'target': 'current',
            }
        return None