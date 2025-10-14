from odoo import fields, models, api, exceptions


class AccountJournal(models.Model):
    _inherit = 'account.journal'


    branch_ids = fields.Many2many('res.company', string="Branch IDs")


    @api.onchange('branch_ids')
    def _onchange_branch_ids(self):
        if self.branch_ids:
            branch_id = self.branch_ids[-1]
            branch_id = int(str(branch_id.id).split('_')[1])

            # raise exceptions.UserError(str(self.branch_ids)+" "+str(self.branch_ids[-1])+" "+str(branch_id)+" "+str(branch_id.id)+" "+str(str(branch_id.id).split('_')[1]))

            records = self.sudo().search([('company_id', '=', branch_id)]).mapped('name')

            # raise exceptions.UserError(str(records))

            if records and self.name not in records:
                self.sudo().create({
                    'name': self.name,
                    'type': self.type,
                    'company_id': branch_id,
                    'default_account_id': self.default_account_id.id,
                    'code': self.code,
                    'currency_id': self.currency_id.id,
                    'restrict_mode_hash_table': self.restrict_mode_hash_table,
                    'suspense_account_id': self.suspense_account_id.id,
                    'profit_account_id': self.profit_account_id.id,
                    'loss_account_id': self.loss_account_id.id,
                    'payment_sequence': self.payment_sequence
                })
            else:
                self.sudo().create({
                    'name': self.name,
                    'type': self.type,
                    'company_id': branch_id,
                    'default_account_id': self.default_account_id.id,
                    'code': self.code,
                    'currency_id': self.currency_id.id,
                    'restrict_mode_hash_table': self.restrict_mode_hash_table,
                    'suspense_account_id': self.suspense_account_id.id,
                    'profit_account_id': self.profit_account_id.id,
                    'loss_account_id': self.loss_account_id.id,
                    'payment_sequence': self.payment_sequence
                })
