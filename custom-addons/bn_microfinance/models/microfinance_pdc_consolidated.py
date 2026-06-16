from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import sql as tools
from datetime import date
import logging

_logger = logging.getLogger(__name__)


class MicrofinancePDCConsolidated(models.Model):
    _name = 'microfinance.pdc.consolidated'
    _description = "Consolidated Post-Dated Cheques"
    _order = 'cheque_date, application_number, installment_number'
    _auto = False  # This is a database view, not a real table

    # Fields from database view
    pdc_id = fields.Many2one('microfinance.pdc', string='PDC Record', readonly=True)
    application_id = fields.Many2one('microfinance', string='Application', readonly=True)
    application_number = fields.Char('Application Number', readonly=True)
    application_state = fields.Selection([
        ('draft', 'Draft'),
        ('hod_approve', 'HOD Approval'),
        ('mem_approve', 'Member Approval'),
        ('approve', 'Approved'),
        ('wfd', 'Waiting For Delivery'),
        ('treasury', 'Treasury'),
        ('in_recovery', 'In Recovery'),
        ('recover', 'Temp Recovered'),
        ('fully_recover', 'Fully Recovered'),
        ('right_of_approval_1', 'Write Off Approval 1'),
        ('right_of_approval_2', 'Write Off Approval 2'),
        ('done', 'Done'),
        ('right_granted', 'Right Granted'),
        ('close', 'Closed'),
        ('reject', 'Rejected'),
    ], string='Application Status', readonly=True)
    
    donee_id = fields.Many2one('res.partner', string='Donee', readonly=True)
    donee_name = fields.Char('Donee Name', readonly=True)
    installment_number = fields.Integer('Installment Number', readonly=True)
    cheque_date = fields.Date('Cheque Date', readonly=True)
    bank_id = fields.Many2one('res.bank', string='Bank', readonly=True)
    bank_name = fields.Char('Bank Name', readonly=True)
    cheque_no = fields.Char('Cheque Number', readonly=True)
    amount = fields.Monetary('Cheque Amount', currency_field='currency_id', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('deposited', 'Deposited'),
        ('cleared', 'Cleared'),
        ('bounced', 'Bounced')
    ], string='State', default='draft', readonly=True)
    deposit_date = fields.Date('Deposit Date', readonly=True)
    notes = fields.Text('Notes', readonly=True)
    
    def init(self):
        """Create the database view"""
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    pdc.id AS id,
                    pdc.id AS pdc_id,
                    pdc.microfinance_id AS application_id,
                    mf.name AS application_number,
                    mf.state AS application_state,
                    mf.donee_id AS donee_id,
                    rp.name AS donee_name,
                    pdc.installment_number AS installment_number,
                    pdc.cheque_date AS cheque_date,
                    pdc.bank_id AS bank_id,
                    pdc.bank_name AS bank_name,
                    pdc.cheque_no AS cheque_no,
                    pdc.amount AS amount,
                    pdc.currency_id AS currency_id,
                    pdc.state AS state,
                    pdc.deposit_date AS deposit_date,
                    pdc.notes AS notes
                FROM
                    microfinance_pdc pdc
                    LEFT JOIN microfinance mf ON pdc.microfinance_id = mf.id
                    LEFT JOIN res_partner rp ON mf.donee_id = rp.id
                WHERE
                    mf.id IS NOT NULL
            )
        """ % self._table)
    
    def action_deposit_cheque(self):
        """
        Deposit cheque action - verifies if deposit date matches current date
        and changes status to Deposited
        """
        self.ensure_one()
        
        # Get the actual PDC record
        pdc_record = self.env['microfinance.pdc'].browse(self.pdc_id.id)
        
        if not pdc_record:
            raise UserError(_('PDC record not found.'))
        
        # Check if cheque is in draft state
        if pdc_record.state != 'draft':
            raise UserError(_('Only draft cheques can be deposited. Current state: %s') % 
                          dict(pdc_record._fields['state'].selection).get(pdc_record.state))
        
        # Get current date
        today = date.today()
        
        # Check if cheque date matches current date
        if pdc_record.cheque_date != today:
            raise UserError(_(
                'Cannot deposit cheque.\n'
                'Cheque Date: %s\n'
                'Current Date: %s\n\n'
                'Cheques can only be deposited on their cheque date.'
            ) % (pdc_record.cheque_date.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')))
        
        # Update the cheque status
        pdc_record.write({
            'state': 'deposited',
            'deposit_date': today,
        })
        
        # Log the deposit
        _logger.info(
            'Cheque deposited: Application=%s, Installment=%s, Amount=%s',
            self.application_number,
            self.installment_number,
            self.amount
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Cheque deposited successfully.\n'
                           'Application: %s\n'
                           'Installment: %s') % (
                    self.application_number,
                    self.installment_number
                ),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_deposit_selected_cheques(self):
        """
        Deposit multiple selected cheques from the tree view
        """
        if not self:
            raise UserError(_('No cheques selected.'))
        
        today = date.today()
        deposited_count = 0
        skipped_count = 0
        error_messages = []
        
        for record in self:
            pdc_record = self.env['microfinance.pdc'].browse(record.pdc_id.id)
            
            if not pdc_record:
                skipped_count += 1
                continue
                
            if pdc_record.state != 'draft':
                error_messages.append(
                    _('App %s, Installment %s: Not in draft state') % 
                    (record.application_number, record.installment_number)
                )
                skipped_count += 1
                continue
            
            if pdc_record.cheque_date != today:
                error_messages.append(
                    _('App %s, Installment %s: Date mismatch (%s)') % 
                    (record.application_number, record.installment_number, 
                     pdc_record.cheque_date.strftime('%Y-%m-%d'))
                )
                skipped_count += 1
                continue
            
            # Deposit the cheque
            pdc_record.write({
                'state': 'deposited',
                'deposit_date': today,
            })
            deposited_count += 1
        
        # Build result message
        if error_messages:
            error_msg = '\n'.join(error_messages[:10])  # Show first 10 errors
            if len(error_messages) > 10:
                error_msg += _('\n... and %s more errors') % (len(error_messages) - 10)
            
            raise UserError(_(
                'Some cheques could not be deposited:\n%s\n\n'
                'Successfully deposited: %s\n'
                'Skipped: %s'
            ) % (error_msg, deposited_count, skipped_count))
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%s cheques deposited successfully.') % deposited_count,
                'type': 'success',
                'sticky': False,
            }
        }