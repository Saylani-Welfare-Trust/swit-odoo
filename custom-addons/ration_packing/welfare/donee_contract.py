# models/donee_contract.py
from odoo import models, fields, api,_
from odoo.exceptions import UserError

class DoneeContract(models.Model):
    _name = 'donee.contract'
    _description = 'Donee Contract'

    name          = fields.Char(string="Contract Reference")
    center_id     = fields.Many2one('res.partner', domain="[('is_donee', '=', True), ('is_recurring', '=', True)]" ,string="Distribution Center", required=True)
    recurring     = fields.Boolean(string="Recurring", default=False)
    state         = fields.Selection([
                      ('draft','Draft'),
                      ('approved','Approved'),
                      ('cancelled','Cancelled'),
                   ], default='draft')
    pack_line_ids = fields.One2many(
                      'donee.contract.line', 'contract_id',
                      string="Pack Lines"
                   )



    @api.model
    def create(self, vals):
        if 'name' not in vals or not vals['name']:
            # Generate the sequence number for mis_no
            vals['name'] = self.env['ir.sequence'].next_by_code('donee.contract') or 'New'
        return super(DoneeContract, self).create(vals)

    def action_approve(self):
        """
        Approve the contract. Raises error if no lines defined.
        """
        for contract in self:
            if not contract.pack_line_ids:
                raise UserError(_('Cannot approve a contract without any pack lines.'))
            contract.state = 'approved'
        return True

    def action_cancel(self):
        """
        Cancel the contract. Only draft or approved contracts can be cancelled.
        """
        for contract in self:
            if contract.state not in ('draft', 'approved'):
                raise UserError(_('Only Draft or Approved contracts can be cancelled.'))
            contract.state = 'cancelled'
        return True

class DoneeContractLine(models.Model):
    _name = 'donee.contract.line'


    _description = 'Donee Contract Line'

    contract_id = fields.Many2one('donee.contract', ondelete='cascade')
    category_id = fields.Many2one('ration.pack.category', string="Pack Category", required=True)

    product_id = fields.Char(
        # related='category_id.product_id',
        string='Product_id',
        required=False)
    quantity    = fields.Integer(string="Quantity", required=True)
