from odoo import _, models, api, fields
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
        ondelete='cascade',
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
        AnalyticAccount = self.env['account.analytic.account']
        for expense in self:
            ids = []
            for key in (expense.analytic_distribution or {}).keys():
                for acc_id in str(key).split(','):
                    acc_id = acc_id.strip()
                    if acc_id.isdigit():
                        ids.append(int(acc_id))

            # Keep only IDs that actually exist in account.analytic.account
            if ids:
                valid_ids = AnalyticAccount.search([('id', 'in', list(set(ids)))]).ids
            else:
                valid_ids = []

            expense.analytic_account_ids = [(6, 0, valid_ids)]

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
    
    # the rules are checked when an expense is saved (form, import or API),
    # not only when the field is changed on the form
    MAX_AGE_DAYS = 90   # about 3 months

    @api.constrains('date')
    def _check_expense_date(self):
        today = fields.Date.context_today(self)
        for expense in self.filtered('date'):
            if expense.date > today:
                raise ValidationError(_('%s: an expense cannot be recorded on a future date.') % expense.name)
            if expense.date < today - timedelta(days=self.MAX_AGE_DAYS):
                raise ValidationError(_('%s: the expense date cannot be older than 3 months.') % expense.name)

    @api.constrains('payment_mode')
    def _check_payment_mode(self):
        for expense in self:
            if expense.payment_mode == 'company_account':
                raise ValidationError(_(
                    '%s: an expense is paid by the employee (to reimburse); '
                    '"Company" cannot be chosen as Paid By.') % expense.name)

    @api.onchange('date')
    def _onchange_date(self):
        # the same rule, shown as soon as the date is typed
        if self.date:
            self._check_expense_date()

    @api.onchange('payment_mode')
    def _onchange_payment_mode(self):
        if self.payment_mode == 'company_account':
            self._check_payment_mode()

    def unlink(self):
        raise UserError(_('You cannot delete an expense.'))