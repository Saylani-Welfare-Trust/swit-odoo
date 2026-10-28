from odoo import models, fields, api, _
from odoo.exceptions import UserError


status_selection = [       
    ('draft', 'Draft'),
    ('posted', 'Posted'),
    ('cancel', 'Cancelled'),
]


class JournalTransfer(models.Model):
    _name = "journal.transfer"
    _description = "Journal Transfer"


    name = fields.Char('Name', default="New")
    descripiton = fields.Char('Description')
    
    session = fields.Char('Session')
    category = fields.Char('Category')
    deposit_slip_no = fields.Char('Deposit Slip No')

    user_id = fields.Many2one('res.users', string="User")
    move_id = fields.Many2one('account.move', string="Account Move")

    date = fields.Date('Transfer Date')
    accounting_date = fields.Date('Accounting Date')
    
    source_journal_id = fields.Many2one('account.journal', string="Source Journal")
    dest_journal_id = fields.Many2one('account.journal', string="Destination Journal")
    currency_id = fields.Many2one('res.currency', string="Currency", default=lambda self: self.env.company.currency_id)
    remarks = fields.Char('Remarks')
    pos_move_id = fields.Many2one('account.move', string="Account Move")

    analytic_account_id = fields.Many2one(related='user_id.employee_id.analytic_account_id', string="Analytci Account", store=True)
    reference = fields.Char('Reference')
    state = fields.Selection(selection=status_selection, string="Status", default="draft")
    
    amount = fields.Monetary('Amount', currency_field='currency_id')
    

    @api.constrains('source_journal_id','dest_journal_id')
    def _check_journals(self):
        for rec in self:
            if rec.source_journal_id == rec.dest_journal_id:
                raise UserError("Source and Destination journals must be different.")

    def action_transfer(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft transfers can be posted (%s).') % rec.name)
            if not rec.source_journal_id.default_account_id or not rec.dest_journal_id.default_account_id:
                raise UserError(_('Both journals of %s need a default account.') % rec.name)

            move_line_vals = [
                {
                    'account_id': rec.dest_journal_id.default_account_id.id,
                    'partner_id': False,
                    'debit': rec.amount,
                    'credit': 0.0,
                    'name': f'Transfer from {rec.source_journal_id.name}',
                },
                {
                    'account_id': rec.source_journal_id.default_account_id.id,
                    'partner_id': False,
                    'debit': 0.0,
                    'credit': rec.amount,
                    'name': f'Transfer to {rec.dest_journal_id.name}',
                },
            ]

            move_vals = {
                'date': rec.date,
                'journal_id': rec.dest_journal_id.id,
                'line_ids': [(0,0,line) for line in move_line_vals],
                'ref': f'Transfer {rec.amount} from {rec.source_journal_id.name} to {rec.dest_journal_id.name}'
            }

            move = rec.env['account.move'].create(move_vals)
            rec.move_id = move.id
            move.action_post()

            rec.state = 'posted'

    def action_cancel(self):
        for rec in self:
            if rec.state == 'cancel':
                raise UserError(_('Entry is already cancelled'))
            # a posted transfer takes its journal entry with it
            if rec.move_id and rec.move_id.state == 'posted':
                rec.move_id.button_draft()
                rec.move_id.button_cancel()
            rec.state = 'cancel'

    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('journal_transfer') or ('New')

        return super(JournalTransfer, self).create(vals)
    
    def action_show_entry(self):
        return {
            "name": _("Journal Entry"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.move_id.id,
        }
    
    def _cron_pull_pos_entries(self):
        records = []

        # 🔥 Fetch POS journal safely
        pos_journal = self.env['account.journal'].search([
            ('type', '=', 'general'),
            ('code', '=', 'POS'),
        ], limit=1)

        if not pos_journal:
            return

        # 🔥 Avoid duplicate DB calls
        existing_move_ids = set(
            self.search([]).mapped('pos_move_id').ids
        )

        moves = self.env['account.move'].search([
            ('journal_id', '=', pos_journal.id),
            ('id', 'not in', list(existing_move_ids)),
            ('state', '=', 'posted'),
        ])


        for move in moves:
            # raise UserError(str(move.name)+" "+str(move.line_ids))

            pos_session = self.env['pos.session'].search([('name', '=', move.ref)])
        
            # 🔥 Pull only meaningful debit lines (receivable preferred)
            debit_lines = move.line_ids.filtered(
                lambda l: l.debit > 0 and l.account_id.account_type in ['asset_receivable', 'asset_cash']
            )

            # a deposit slip that went negative (cheque returns) is a credit
            # line: pulled as a negative transfer, reversing that bank's deposit
            credit_lines = move.line_ids.filtered(
                lambda l: l.credit > 0 and l.bank_journal_id and l.account_id.account_type in ['asset_receivable', 'asset_cash']
            )

            for line in debit_lines | credit_lines:
                # Parse the line name to break it into 3 parts
                line_name = line.name or move.ref or move.name or ''
                parts = [part.strip() for part in line_name.split(' - ')]
                
                session_val = parts[0] if len(parts) > 0 else ''
                category_val = parts[1] if len(parts) > 1 else ''
                deposit_slip_val = parts[2] if len(parts) > 2 else ''

                records.append({
                    'pos_move_id': move.id,
                    'accounting_date': move.date,
                    'descripiton': line_name, # Keeping original for reference
                    'session': session_val,            # New field
                    'category': category_val,          # New field
                    'deposit_slip_no': deposit_slip_val, # New field
                    'reference': line.name.rsplit(' - ', 1)[-1].strip() if line.name else '',                    
                    'source_journal_id': move.journal_id.id,
                    'dest_journal_id': line.bank_journal_id.id,
                    'date': line.date,
                    'amount': line.debit - line.credit,
                    'user_id': pos_session.user_id.id,
                })
        
        if records:
            self.create(records)
