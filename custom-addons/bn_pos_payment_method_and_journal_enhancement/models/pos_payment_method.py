from odoo import fields, models, api


class POSPaymentMethod(models.Model):
    _inherit= 'pos.payment.method'


    branch_ids = fields.Many2many('res.company', string="Branch IDs")


    @api.onchange('branch_ids')
    def _onchange_branch_ids(self):
        if self.branch_ids:
            branch_id = self.branch_ids[-1]
            branch_id = int(str(branch_id.id).split('_')[1])

            # raise exceptions.UserError(str(self.branch_ids)+" "+str(self.branch_ids[-1])+" "+str(branch_id)+" "+str(branch_id.id)+" "+str(str(branch_id.id).split('_')[1]))

            records = self.sudo().search([('company_id', '=', branch_id)]).mapped('name')
            journal_obj = self.env['account.journal'].sudo().search([('company_id', '=', branch_id),('name', '=', self.journal_id.name)])

            # raise exceptions.UserError(str(records))

            if records and self.name not in records:
                self.sudo().create({
                    'name': self.name,
                    'is_online_payment': self.is_online_payment,
                    'company_id': branch_id,
                    'split_transactions': self.split_transactions,
                    'stock_in': self.stock_in,
                    'journal_id': journal_obj.id,
                    'receivable_account_id': self.receivable_account_id.id,
                    'outstanding_account_id': self.outstanding_account_id.id
                })
            else:
                self.sudo().create({
                    'name': self.name,
                    'is_online_payment': self.is_online_payment,
                    'company_id': branch_id,
                    'split_transactions': self.split_transactions,
                    'stock_in': self.stock_in,
                    'journal_id': journal_obj.id,
                    'receivable_account_id': self.receivable_account_id.id,
                    'outstanding_account_id': self.outstanding_account_id.id
                })