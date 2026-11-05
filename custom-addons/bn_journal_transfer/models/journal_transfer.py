from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

status_selection = [       
    ('draft', 'Draft'),
    ('posted', 'Posted'),
    ('cancel', 'Cancelled'),
]


class JournalTransfer(models.Model):
    _name = "journal.transfer"
    _inherit = ['pos.link.mixin']
    _description = "Journal Transfer"


    name = fields.Char('Name', default="New")
    descripiton = fields.Char('Description')
    
    session = fields.Char('Session')
    category = fields.Char('Category')
    deposit_slip_no = fields.Char('Deposit Slip No')

    user_id = fields.Many2one('res.users', string="User")
    move_id = fields.Many2one('account.move', string="Account Move")

    date = fields.Date('Transfer Date', index=True)
    accounting_date = fields.Date('Accounting Date')
    
    source_journal_id = fields.Many2one('account.journal', string="Source Journal")
    dest_journal_id = fields.Many2one('account.journal', string="Destination Journal")
    currency_id = fields.Many2one('res.currency', string="Currency", default=lambda self: self.env.company.currency_id)
    remarks = fields.Char('Remarks')
    pos_move_id = fields.Many2one('account.move', string='POS Session Entry')

    analytic_account_id = fields.Many2one(related='user_id.employee_id.analytic_account_id', string="Analytci Account", store=True)
    reference = fields.Char('Reference')
    state = fields.Selection(selection=status_selection, string="Status", default="draft")
    
    amount = fields.Monetary('Amount', currency_field='currency_id')
    

    @api.constrains('source_journal_id','dest_journal_id')
    def init(self):
        # transfers pulled before the link existed: the session of their POS entry
        self.env.cr.execute("""
            UPDATE journal_transfer t SET pos_session_id = s.id
              FROM pos_session s
             WHERE s.move_id = t.pos_move_id AND t.pos_session_id IS NULL
        """)
        super().init()

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

            move = rec.env['account.move'].with_context(default_source_ref='%s,%s' % (rec._name, rec.id)).create(move_vals)
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
    
    @api.model
    def _pull_pos_entries(self, moves=None):
        """Pulls POS entries. Can be called with specific moves (from Cheque Clear) 
           or without arguments to act like a Cron job and pull all pending moves."""
        records = []

        if moves is None:
            # Fallback: Acts exactly like your old cron job
            pos_journal = self.env['account.journal'].search([
                ('type', '=', 'general'),
                ('code', '=', 'POS'),
            ], limit=1)

            if not pos_journal:
                return

            existing_move_ids = set(self.search([]).mapped('pos_move_id').ids)

            moves = self.env['account.move'].search([
                ('journal_id', '=', pos_journal.id),
                ('id', 'not in', list(existing_move_ids)),
                ('state', '=', 'posted'),
            ])
        else:
            # If specific moves are passed, filter out any that were already processed
            existing_move_ids = set(self.search([('pos_move_id', 'in', moves.ids)]).mapped('pos_move_id').ids)
            moves = moves.filtered(lambda m: m.id not in existing_move_ids and m.state == 'posted')

        for move in moves:
            pos_session = self.env['pos.session'].search([('move_id', '=', move.id)], limit=1) \
                or self.env['pos.session'].search([('name', '=', move.ref)], limit=1)
        
            debit_lines = move.line_ids.filtered(
                lambda l: l.debit > 0 and l.account_id.account_type in ['asset_receivable', 'asset_cash']
            )

            credit_lines = move.line_ids.filtered(
                lambda l: l.credit > 0 and l.bank_journal_id and l.account_id.account_type in ['asset_receivable', 'asset_cash']
            )

            for line in debit_lines | credit_lines:
                line_name = line.name or move.ref or move.name or ''
                parts = [part.strip() for part in line_name.split(' - ')]
                
                session_val = parts[0] if len(parts) > 0 else ''
                category_val = parts[1] if len(parts) > 1 else ''
                deposit_slip_val = parts[2] if len(parts) > 2 else ''

                records.append({
                    'pos_move_id': move.id,
                    'accounting_date': move.date,
                    'descripiton': line_name,
                    'session': session_val,
                    'category': category_val,
                    'deposit_slip_no': deposit_slip_val,
                    'reference': line.name.rsplit(' - ', 1)[-1].strip() if line.name else '',                    
                    'source_journal_id': move.journal_id.id,
                    'dest_journal_id': line.bank_journal_id.id if line.bank_journal_id else move.journal_id.id,
                    'date': line.date,
                    'amount': line.debit - line.credit,
                    'user_id': pos_session.user_id.id if pos_session else False,
                    'pos_session_id': pos_session.id,
                })
        
        if records:
            self.create(records)
            

    @api.model
    def _split_description(self):
        """Upgrade hook (data/upgrade_hooks.xml): fill session / category /
        deposit slip of the older transfers from their description
        "<session> - <category> - <slip>". Only rows not done yet."""
        self.env.cr.execute("""
            UPDATE journal_transfer
               SET session         = NULLIF(TRIM(SPLIT_PART(descripiton, ' - ', 1)), ''),
                   category        = NULLIF(TRIM(SPLIT_PART(descripiton, ' - ', 2)), ''),
                   deposit_slip_no = NULLIF(TRIM(SPLIT_PART(descripiton, ' - ', 3)), '')
             WHERE descripiton IS NOT NULL AND descripiton <> '' AND session IS NULL
        """)
        if self.env.cr.rowcount:
            _logger.info("journal.transfer: session / category / slip filled on %s transfers", self.env.cr.rowcount)
            self.invalidate_model(['session', 'category', 'deposit_slip_no'])
