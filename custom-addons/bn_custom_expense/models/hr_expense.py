from odoo import models, api, fields
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError


from datetime import timedelta


class HRExpense(models.Model):
    _inherit = 'hr.expense'


    analytic_account_ids = fields.Many2many(
        comodel_name='account.analytic.account',
        relation='hr_expense_analytic_account_rel',
        column1='expense_id',
        column2='analytic_account_id',
        string='Analytic Accounts',
        compute='_compute_analytic_account_ids',
        store=True,
        readonly=True,
    )

    analytic_province_id = fields.Many2one(
        'account.analytic.account', string='Province',
        compute='_compute_analytic_levels', store=True, readonly=True,
    )
    analytic_city_id = fields.Many2one(
        'account.analytic.account', string='City',
        compute='_compute_analytic_levels', store=True, readonly=True,
    )
    analytic_zone_id = fields.Many2one(
        'account.analytic.account', string='Zone',
        compute='_compute_analytic_levels', store=True, readonly=True,
    )
    analytic_branch_id = fields.Many2one(
        'account.analytic.account', string='Branch',
        compute='_compute_analytic_levels', store=True, readonly=True,
    )

    @api.depends('analytic_distribution')
    def _compute_analytic_account_ids(self):
        for expense in self:
            ids = []
            for key in (expense.analytic_distribution or {}).keys():
                for acc_id in str(key).split(','):
                    acc_id = acc_id.strip()
                    if acc_id.isdigit():
                        ids.append(int(acc_id))
            expense.analytic_account_ids = [(6, 0, list(set(ids)))]

    @api.depends('analytic_account_ids', 'analytic_account_ids.location_option_id')
    def _compute_analytic_levels(self):
        AA = self.env['account.analytic.account']
        # Detect the parent field dynamically so the module never crashes
        parent_field = next(
            (f for f in ('parent_id', 'parent_analytic_account_id', 'parent_account_id')
             if f in AA._fields),
            None,
        )
        for expense in self:
            province = city = zone = branch = AA
            for acc in expense.analytic_account_ids:
                node = acc
                seen = set()
                while node and node.id not in seen:
                    seen.add(node.id)
                    lvl = (node.location_option_id.name or '').strip()
                    if lvl == 'Province' and not province:
                        province = node
                    elif lvl == 'City' and not city:
                        city = node
                    elif lvl == 'Zone' and not zone:
                        zone = node
                    elif lvl == 'Branch' and not branch:
                        branch = node
                    node = getattr(node, parent_field, AA) if parent_field else AA
            expense.analytic_province_id = province
            expense.analytic_city_id = city
            expense.analytic_zone_id = zone
            expense.analytic_branch_id = branch
    
    @api.onchange('date')
    def _onchange_date(self):
        if self.date:
            today = fields.Date.today()
            three_months_ago = today - timedelta(days=90)  # roughly 3 months

            if self.date > today:
                raise ValidationError('Expense cannot be recorded on future dates.')

            if self.date < three_months_ago:
                raise ValidationError('Expense date cannot be older than 3 months.')
    
    @api.onchange('payment_mode')
    def _onchange_payment_mode(self):
        if self.payment_mode == 'company_account':
            raise ValidationError('Expense payment mode can be set as ( Company ).')
        
    def unlink(self):
        raise UserError(_('You cannot delete an expense.'))
        # if self.state == 'approved':
        #     raise ValidationError('No one have right to delete an approved expense.')
        
        # return super(HRExpense, self).unlink()