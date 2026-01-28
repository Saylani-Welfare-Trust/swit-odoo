from odoo import models, fields, api, _
from odoo.exceptions import UserError


status_selection = [       
    ('draft', 'Draft'),
    ('posted', 'Posted'),
    ('cancel', 'Cancelled'),
]


class JournalTransfer(models.TransientModel):
    _name = "journal.transfer"
    _description = "Journal Transfer"


    name = fields.Char('Name', default="New")
    descripiton = fields.Char('Description')

    user_id = fields.Many2one('res.users', string="User")
    move_id = fields.Many2one('account.move', string="Account Move")

    date = fields.Date('Transfer Date')
    
    source_journal_id = fields.Many2one('account.journal', string="Source Journal")
    dest_journal_id = fields.Many2one('account.journal', string="Destination Journal")
    currency_id = fields.Many2one('res.currency', string="Currency", default=lambda self: self.env.company.currency_id)

    pos_move_id = fields.Many2one('account.move', string="Account Move")

    state = fields.Selection(selection=status_selection, string="Status", default="draft")
    
    amount = fields.Monetary('Amount', currency_field='currency_id')
    

    @api.constrains('source_journal_id','dest_journal_id')
    def _check_journals(self):
        for rec in self:
            if rec.source_journal_id == rec.dest_journal_id:
                raise UserError("Source and Destination journals must be different.")

    def action_transfer(self):
        self.ensure_one()
        move_line_vals = [
            {
                'account_id': self.dest_journal_id.default_account_id.id,
                'partner_id': False,
                'debit': self.amount,
                'credit': 0.0,
                'name': f'Transfer from {self.source_journal_id.name}',
            },
            {
                'account_id': self.source_journal_id.default_account_id.id,
                'partner_id': False,
                'debit': 0.0,
                'credit': self.amount,
                'name': f'Transfer to {self.dest_journal_id.name}',
            },
        ]

        move_vals = {
            'date': self.date,
            'journal_id': self.source_journal_id.id,
            'line_ids': [(0,0,line) for line in move_line_vals],
            'ref': f'Transfer {self.amount} from {self.source_journal_id.name} to {self.dest_journal_id.name}'
        }

        move = self.env['account.move'].create(move_vals)
        self.move_id = move.id
        move.post()

        self.state = 'posted'

    def action_cancel(self):
        self.state = 'cancel'

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
                lambda l: l.debit > 0 and l.account_id.account_type == 'asset_receivable'
            )
        
            for line in debit_lines:
                records.append({
                    'pos_move_id': move.id,
                    'descripiton': line.name or move.ref or move.name,
                    'source_journal_id': move.journal_id.id,
                    'dest_journal_id': line.bank_journal_id.id,
                    'amount': line.debit,
                    'user_id': pos_session.user_id.id,
                })

        # raise UserError(str(records))
    
        if records:
            self.create(records)
                
