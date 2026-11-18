import logging

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

from .sadqa_jariya_line import collection_point_selection

_logger = logging.getLogger(__name__)

state_selection = [
    ('draft', 'Draft'),
    ('delivered', 'Delivery Created'),
    ('pending', 'Pending'),
    ('collected', 'Collected'),
    ('disbursed', 'Disbursed'),
    ('return', 'Returned'),
]


class SadqaJariyaRecurringLine(models.Model):
    _name = 'sadqa.jariya.recurring.line'
    _description = 'Sadqa e Jariya Recurring Line'
    _order = 'collection_date, id'

    application_id = fields.Many2one('sadqa.jariya', string='Application', ondelete='cascade')
    name = fields.Char('Name', related='application_id.name', store=True)
    donee_id = fields.Many2one(related='application_id.donee_id', string='Donee', store=True)
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)

    application_type_id = fields.Many2one('sadqa.jariya.application.type', string='Disbursement Application Type')
    disbursement_category_id = fields.Many2one('sadqa.jariya.disbursement.category', string='Disbursement Category')
    product_id = fields.Many2one('product.product', string='Product')

    collection_point = fields.Selection(collection_point_selection, string='Collection Point')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Branch')
    collection_date = fields.Date('Collection Date', default=fields.Date.context_today)

    quantity = fields.Float('Quantity', default=1.0)
    amount = fields.Monetary('Amount', currency_field='currency_id')
    state = fields.Selection(state_selection, string='State', default='draft')
    bill_id = fields.Many2one('account.move', string='Bill', readonly=True)
    show_deliver_button = fields.Boolean('Show Deliver Button', compute='_compute_show_deliver_button')

    media_ids = fields.Many2many(
        'ir.attachment',
        'sadqa_jariya_recurring_line_media_rel',
        'recurring_line_id',
        'attachment_id',
        string='Media (Images/Videos)',
    )
    media_count = fields.Integer(compute='_compute_media_count', string='Media Count')

    @api.depends('media_ids')
    def _compute_media_count(self):
        for rec in self:
            rec.media_count = len(rec.media_ids)

    @api.depends('disbursement_category_id', 'state')
    def _compute_show_deliver_button(self):
        for rec in self:
            rec.show_deliver_button = rec.disbursement_category_id.name == 'In Kind' and rec.state not in ['delivered', 'disbursed']

    @api.onchange('disbursement_category_id')
    def _onchange_disbursement_category_id(self):
        if self.disbursement_category_id.name == 'In Kind':
            self.collection_point = 'branch'
        elif self.disbursement_category_id.name == 'Bank':
            self.collection_point = 'bank'

    @api.model
    def _auto_mark_as_delivered_today(self):
        """Scheduled action: deliveries for recurring In Kind lines due by today"""
        lines = self.search([
            ('collection_date', '<=', fields.Date.today()),
            ('state', '=', 'draft'),
            ('disbursement_category_id.name', '=', 'In Kind'),
            ('application_id.state', '=', 'recurring'),
            # empty: In Kind lines whose branch was never filled in (read-only for In Kind)
            ('collection_point', 'in', ['branch', False]),
        ])
        for line in lines:
            try:
                with self.env.cr.savepoint():
                    line.action_delivered()
            except Exception:
                _logger.exception("Could not create delivery for Sadqa e Jariya %s recurring line %s", line.name, line.id)

    @api.model
    def _auto_create_bank_bills(self):
        """Scheduled action: bills for recurring Bank lines due on their collection date"""
        lines = self.search([
            ('collection_date', '=', fields.Date.today()),
            ('state', '=', 'draft'),
            ('disbursement_category_id.name', '=', 'Bank'),
            ('collection_point', '=', 'bank'),
            ('bill_id', '=', False),
            # recurring lines exist once Create Recurring Orders moved the application to Recurring
            ('application_id.state', '=', 'recurring'),
        ])
        for line in lines:
            try:
                with self.env.cr.savepoint():
                    line._create_bill()
                    line.state = 'delivered'
            except Exception:
                _logger.exception("Could not create bill for Sadqa e Jariya recurring line %s", line.id)

    def _create_bill(self):
        self.ensure_one()
        if not self.donee_id:
            return
        account = self.product_id.property_account_expense_id or self.product_id.categ_id.property_account_expense_categ_id
        if not account:
            account = self.env['account.account'].search([('account_type', '=', 'expense')], limit=1)
        line_vals = {
            'product_id': self.product_id.id,
            'name': self.product_id.name or 'Sadqa e Jariya Payment',
            'quantity': self.quantity,
            'price_unit': self.amount,
            'account_id': account.id,
            # a disbursement, no vendor taxes from the product
            'tax_ids': [(6, 0, [])],
        }
        if self.analytic_account_id:
            line_vals['analytic_distribution'] = {str(self.analytic_account_id.id): 100}
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.donee_id.id,
            'invoice_date': self.collection_date,
            'date': self.collection_date,
            'ref': self.name,
            'invoice_line_ids': [(0, 0, line_vals)],
            'sadqa_jariya_recurring_line_id': self.id,
        })
        self.bill_id = bill
        bill.action_post()
        return bill

    def action_delivered(self):
        for line in self.filtered(lambda l: l.disbursement_category_id.name == 'In Kind'):
            if line.state != 'draft':
                raise ValidationError(_('A delivery is only created for a Draft line (%s).') % line.display_name)
            # the Sadqa e Jariya Delivery operation type of the user's warehouse
            picking_type = self.env['stock.warehouse']._get_program_type('sadqa_jariya')
            location_src = picking_type.default_location_src_id or picking_type.warehouse_id.lot_stock_id
            location_dest = picking_type.default_location_dest_id or self.env.ref('stock.stock_location_customers')
            picking = self.env['stock.picking'].create({
                'partner_id': line.donee_id.id,
                'picking_type_id': picking_type.id,
                'location_id': location_src.id,
                'location_dest_id': location_dest.id,
                'origin': line.name,
                'sadqa_jariya_recurring_line_id': line.id,
                'source_record_ref': '%s,%s' % (line.application_id._name, line.application_id.id) if line.application_id else False,
            })
            move = self.env['stock.move'].create({
                'name': line.product_id.display_name,
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity,
                'product_uom': line.product_id.uom_id.id,
                'picking_id': picking.id,
                'location_id': location_src.id,
                'location_dest_id': location_dest.id,
            })
            self.env['stock.move.line'].create({
                'move_id': move.id,
                'product_id': line.product_id.id,
                'product_uom_id': line.product_id.uom_id.id,
                'quantity': line.quantity,
                'picking_id': picking.id,
                'location_id': location_src.id,
                'location_dest_id': location_dest.id,
            })
            picking.action_assign()
            line.state = 'delivered'

    def action_disbursed(self):
        """Mark the recurring line as disbursed."""
        for line in self:
            if line.state not in ['draft', 'delivered']:
                raise ValidationError(_(
                    "This recurring line cannot be paid again. Current state is '%s'. "
                    "Only Draft or Delivery Created lines can be paid."
                ) % line.state)
            line.state = 'disbursed'
        self.application_id._auto_disburse_if_all_lines_delivered()
        return True

    def write(self, vals):
        res = super().write(vals)
        if vals.get('state') == 'disbursed':
            self.application_id._auto_disburse_if_all_lines_delivered()
        return res

    def open_recurring_disbursement_popup(self):
        self.ensure_one()
        popup = self.env['sadqa.jariya.recurring.line.disbursement.popup'].create({
            'recurring_line_id': self.id,
            'media_ids': [(6, 0, self.media_ids.ids)],
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Recurring Disbursement Details'),
            'res_model': 'sadqa.jariya.recurring.line.disbursement.popup',
            'res_id': popup.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_return_to_draft(self):
        """Returned line back to draft, the application back to Recurring"""
        if self.filtered(lambda l: l.state != 'return'):
            raise ValidationError(_("Only lines in 'Return' state can be moved back to Draft."))
        self.write({'state': 'draft'})
        self.application_id.write({'state': 'recurring'})
        return {'type': 'ir.actions.client', 'tag': 'reload'}
