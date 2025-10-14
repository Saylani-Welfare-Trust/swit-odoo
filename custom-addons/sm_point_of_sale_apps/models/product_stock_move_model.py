from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import date, datetime, time
from markupsafe import Markup
from odoo.fields import Command


status_selection = [
    ('draft', 'Draft'),
    ('validate', 'Validate'),
    ('box_open', 'Open Box'),
    ('valuation_committee', 'Valuation Committee'),
    ('approval', 'Approval'),
    ('box_validate', 'Box Validate'),
    ('cancel', 'Cancelled')
]

type_selection = [
    ('default', 'Default'),
    ('yes', 'Yes'),
    ('no', 'No'),
]

class ProductStockMoveModel(models.Model):
    _name = 'product.stock.move'
    _inherit = ['mail.thread']
    _description = 'Product Stock Move Model'
    _rec_name = 'name'

    def default_set_value(self, name):
        product_stock_move_config = self.env['product.stock.move.config'].sudo().search([], limit=1)
        if product_stock_move_config:
            field_map = {
                'location_id': product_stock_move_config.location_id.id,
                'stock_picking_type_id': product_stock_move_config.stock_picking_type_id.id,
                'journal_id': product_stock_move_config.journal_id.id,
                'debit_account_id': product_stock_move_config.debit_account_id.id,
                'credit_account_id': product_stock_move_config.credit_account_id.id
            }
            return field_map.get(name, False)
        return False

    partner_id = fields.Many2one(comodel_name='res.partner', string='Customer', required=True)
    location_id = fields.Many2one(comodel_name='stock.location', string='Location', required=True, domain="[('usage', '=', 'internal')]", default=lambda self: self.default_set_value('location_id'))
    stock_picking_type_id = fields.Many2one(comodel_name='stock.picking.type', string='Operations Types', domain="[('code', '=', 'incoming')]", default=lambda self: self.default_set_value('stock_picking_type_id'))
    journal_id = fields.Many2one(comodel_name='account.journal', string='Journal', required=True, domain="[('type', '=', 'sale')]", default=lambda self: self.default_set_value('journal_id'))
    product_id = fields.Many2one(comodel_name='product.product', string='Product', required=True, domain="[('detailed_type', '=', 'product')]")
    quantity = fields.Float(string='Quantity', required=True, default="1")
    state = fields.Selection(selection=status_selection, string='Status', default='draft')
    product_stock_move_lines = fields.One2many(comodel_name='product.stock.move.lines', inverse_name='product_stock_move_id', string='Product Stock Move Lines')
    product_valuation_lines = fields.One2many(comodel_name='product.valuation.lines', inverse_name='product_stock_move_id', string='Product Valuation Lines')
    company_id = fields.Many2one(comodel_name='res.company', string='Company', default=lambda self: self.env.company)
    name = fields.Char(string="Reference", default=lambda self: _('New'))
    debit_account_id = fields.Many2one(comodel_name='account.account', string='Account (Dr)', required=True, domain="[('account_type', 'in', ['asset_receivable', 'asset_cash', 'asset_current', 'asset_non_current', 'asset_prepayments', 'asset_fixed'])]", default=lambda self: self.default_set_value('debit_account_id'))
    credit_account_id = fields.Many2one(comodel_name='account.account', string='Account (Cr)', required=True, domain="[('account_type', 'in', ['income', 'income_other'])]", default=lambda self: self.default_set_value('credit_account_id'))
    account_move_id = fields.Many2one(comodel_name='account.move', string='Account Move')
    reverse_account_move_id = fields.Many2one(comodel_name='account.move', string='Reverse Account Move')
    check_bool = fields.Selection(selection=type_selection, string='Check Bool', default='default')
    picking_id = fields.Many2one(comodel_name='stock.picking', string='Stock Picking', domain="[('picking_type_id', '=', stock_picking_type_id)]")
    picking_list_id = fields.Many2one(comodel_name='stock.picking', string='Stock Picking List', domain="[('picking_type_id', '=', stock_picking_type_id)]")
    account_move_list_id = fields.Many2one(comodel_name='account.move', string='Account Move List')

    @api.constrains('partner_id')
    def compute_partner_id(self):
        for record in self:
            if record.name == 'New':
                record.name = self.env['ir.sequence'].next_by_code('product.stock.move.sequence')

    @api.constrains('partner_id', 'product_id', 'quantity')
    def compute_quantity(self):
        for record in self:
            if record.quantity == 0.0:
                raise UserError('Quantity cannot be zero.')
            if not record.quantity:
                raise UserError('Quantity is missing or invalid.')

    def name_get(self):
        result = []
        for record in self:
            name = f'{record.product_id.name}'
            result.append((record.id, name))
        return result

    def unlink(self):
        for record in self:
            if record.state != 'cancel':
                raise UserError("You cannot delete a record that is in the 'Cancelled' state.")
        return super(ProductStockMoveModel, self).unlink()

    def action_validate(self):
        for record in self:
            if not record.stock_picking_type_id:
                raise UserError('Please Select Stock Picking Type')
            if record.stock_picking_type_id.default_location_src_id:
                vendor_location_id = record.stock_picking_type_id.default_location_src_id.id
            elif record.partner_id.property_stock_supplier:
                vendor_location_id = record.partner_id.property_stock_supplier.id
            else:
                vendor_location_id = False
            if not vendor_location_id:
                raise UserError('Please Select Vendor Location')
            move_ids = []
            stock_picking = self.env['stock.picking'].sudo().search([('id', '=', record.picking_id.id), ('picking_type_id', '=', record.stock_picking_type_id.id)])
            if not stock_picking:
                move_ids.append((0, 0, {
                    'product_id': record.product_id.id,
                    'description_picking': record.product_id.name,
                    'name': record.product_id.name,
                    'product_uom_qty': record.quantity,
                    'location_dest_id': record.location_id.id,
                    'location_id': vendor_location_id,
                }))
                move_vals = {
                    'partner_id': record.partner_id.id,
                    'picking_type_id': record.stock_picking_type_id.id,
                    'location_dest_id': record.location_id.id,
                    'location_id': vendor_location_id,
                    'scheduled_date': fields.Datetime.today(),
                    'origin': record.name,
                    'move_ids_without_package': move_ids,
                }
                picking_id = self.env['stock.picking'].sudo().create(move_vals)
                if picking_id:
                    record.write({
                        'picking_id': picking_id.id,
                    })
                    picking_id.button_validate()
            if not record.journal_id:
                raise UserError('Please Select Journal')
            box_lines = [
                {
                    'account_id': record.debit_account_id.id,
                    'partner_id': record.partner_id.id,
                    'journal_id': record.journal_id.id,
                    'name': 'Box',
                    'debit': 1.0,
                    'credit': 0.0,
                },
                {
                    'account_id': record.credit_account_id.id,
                    'partner_id': record.partner_id.id,
                    'journal_id': record.journal_id.id,
                    'name': 'Box',
                    'debit': 0.0,
                    'credit': 1.0,
                }
            ]
            box_lines_tuples = [(0, 0, line) for line in box_lines]
            vals = {
                'ref': record.name,
                'partner_id': record.partner_id.id,
                'date': date.today(),
                'journal_id': record.journal_id.id,
                'line_ids': box_lines_tuples,
            }
            account_move = self.env['account.move'].sudo().create(vals)
            if account_move:
                account_move.action_post()
                record.write({
                    'account_move_id': account_move.id
                })
            record.write({
                'state': 'validate',
            })

    def action_cancel(self):
        for record in self:
            record.write({
                'state': 'cancel',
            })

    def action_box_open(self):
        for record in self:
            record.write({
                'state': 'box_open',
            })

    @api.constrains('product_stock_move_lines', 'product_stock_move_lines.quantity')
    def constrains_product_stock_move_lines(self):
        for record in self:
            for move_lines in record.product_stock_move_lines:
                if move_lines.quantity == 0.0:
                    raise UserError('Quantity cannot be zero.')
                elif not move_lines.quantity:
                    raise UserError('Quantity is missing or invalid.')

    def action_check(self):
        for record in self:
            if not record.product_stock_move_lines:
                raise UserError("No product stock move lines to process.")
            for move_lines in record.product_stock_move_lines:
                if move_lines.quantity == 0.0:
                    raise UserError('Quantity cannot be zero.')
                elif not move_lines.quantity:
                    raise UserError('Quantity is missing or invalid.')
                if move_lines.avg_price == 0.0:
                    move_lines.check_price_bool = True
                elif not move_lines.avg_price:
                    move_lines.check_price_bool = True
                else:
                    move_lines.check_price_bool = False
            for lines in record.product_stock_move_lines:
                if lines.avg_price == 0.0:
                    record.check_bool = 'yes'
                    break
                elif not lines.avg_price:
                    record.check_bool = 'yes'
                    break
                else:
                    record.check_bool = 'no'

    def _get_html_link_product_stock_move(self, title=None):
        self.ensure_one()
        return Markup("<a href=# data-oe-model='%s' data-oe-id='%s'>%s <i class='fa fa-check'></i></a>") % (
            self._name, self.id, title or self.display_name)

    def message_post_to_product_stock_move(self, users):
        for record in self.with_company(self.company_id):
            subject = f"Approval ({users.name})"
            body = _("This status of the 'Warehouses Stock' has changed to 'Approval' %s.", record._get_html_link_product_stock_move())
            mail_message = self.env['mail.message'].sudo().search([('author_id', '=', users.partner_id.id)], limit=1)
            if mail_message:
                parent_id = mail_message.id
            else:
                parent_id = False
            record.message_post(
                body=body,
                subject=subject,
                message_type='notification',
                email_from=self.env.user.partner_id.email,
                author_id=self.env.user.partner_id.id,
                parent_id=parent_id,
                subtype_xmlid='mail.mt_comment',
                subtype_id=self.env.ref('mail.mt_comment').id,
                partner_ids=users.partner_id.mapped('id')
            )

    def message_notify_to_product_stock_move(self, users):
        for record in self.with_company(self.company_id):
            subject = f"Approval ({users.name})"
            body = _("This status of the 'Warehouses Stock' has changed to 'Approval' %s.", record._get_html_link_product_stock_move())
            record.message_notify(
                body=body,
                subject=subject,
                author_id=self.env.user.partner_id.id,
                email_from=self.env.user.partner_id.email,
                model=self._name,
                res_id=record.id,
                subtype_xmlid='mail.mt_comment',
                subtype_id=self.env.ref('mail.mt_comment').id,
                email_layout_xmlid='mail.mail_notification_layout',
                partner_ids=users.partner_id.mapped('id')
            )

    def action_valuation_committee(self):
        for record in self:
            if not record.product_stock_move_lines:
                raise UserError("No product stock move lines to process.")
            approval = self.env['res.groups'].sudo().search([('id', '=', self.env.ref('sm_point_of_sale_apps.approval_res_groups').id)])
            if approval:
                for lines in approval.users:
                    self.message_post_to_product_stock_move(lines)
                    self.message_notify_to_product_stock_move(lines)
            for move_lines in record.product_stock_move_lines.filtered(lambda rec: rec.check_price_bool == True):
                product_valuation_lines = self.env['product.valuation.lines'].sudo().search([('product_stock_move_id', '=', move_lines.product_stock_move_id.id), ('product_id', '=', move_lines.product_id.id), ('location_id', '=', move_lines.location_id.id)])
                if product_valuation_lines:
                    for lines in product_valuation_lines:
                        lines.write({
                            'product_id': move_lines.product_id.id,
                            'location_id': move_lines.location_id.id,
                            'quantity': move_lines.quantity,
                            'avg_price': move_lines.avg_price,
                            'check_price_bool': True,
                            'company_id': self.env.company.id,
                            'product_stock_move_id': record.id,
                            'product_stock_move_line_id': move_lines.id,
                        })
                else:
                    self.env['product.valuation.lines'].sudo().create({
                        'product_id': move_lines.product_id.id,
                        'location_id': move_lines.location_id.id,
                        'quantity': move_lines.quantity,
                        'avg_price': move_lines.avg_price,
                        'check_price_bool': True,
                        'company_id': self.env.company.id,
                        'product_stock_move_id': record.id,
                        'product_stock_move_line_id': move_lines.id,
                    })
            record.write({
                'state': 'valuation_committee',
            })

    def action_approval(self):
        for record in self:
            if not record.product_stock_move_lines:
                raise UserError("No product stock move lines to process.")
            if not record.product_valuation_lines:
                raise UserError("No product valuation lines to process.")
            for lines in record.product_valuation_lines:
                if lines.avg_price == 0.0:
                    raise UserError("The average price cannot be 0. Please check the valuation lines.")
                    break
                elif not lines.avg_price:
                    raise UserError("The average price is missing. Please ensure all valuation have a price.")
                    break
            for valuation_lines in record.product_valuation_lines:
                valuation_lines.product_id.write({
                    'lst_price': valuation_lines.avg_price
                })
                stock_move = self.env['product.stock.move.lines'].sudo().search([('id', '=', valuation_lines.product_stock_move_line_id.id), ('product_stock_move_id', '=', valuation_lines.product_stock_move_id.id), ('product_id', '=', valuation_lines.product_id.id), ('location_id', '=', valuation_lines.location_id.id)])
                for stock_move_lines in stock_move:
                    stock_move_lines.write({
                        'avg_price': valuation_lines.avg_price
                    })
            record.write({
                'state': 'approval',
            })

    def action_box_validate(self):
        for record in self:
            if not record.product_stock_move_lines:
                raise UserError("No product stock move lines to process.")
            if not record.journal_id:
                raise UserError('Please Select Journal')
            if not record.stock_picking_type_id:
                raise UserError('Please Select Stock Picking Type')
            if record.stock_picking_type_id.default_location_src_id:
                vendor_location_id = record.stock_picking_type_id.default_location_src_id.id
            elif record.partner_id.property_stock_supplier:
                vendor_location_id = record.partner_id.property_stock_supplier.id
            else:
                vendor_location_id = False
            if not vendor_location_id:
                raise UserError('Please Select Vendor Location')
            if record.account_move_id:
                reverse_account_id = self.env['account.move.reversal'].sudo().search([('move_ids', 'in', [record.account_move_id.id])])
                if reverse_account_id:
                    raise UserError('A reversal already exists for this account move, operation cannot be completed.')
                account_move_reversal = self.env['account.move.reversal'].sudo().create({
                    'journal_id': record.journal_id.id,
                    'date': fields.Date.today(),
                    'move_type': 'entry',
                    'move_ids': [(4, record.account_move_id.id)]
                })
                if account_move_reversal:
                    account_move_reversal.refund_moves()
                reverse_id = self.env['account.move'].sudo().search([('reversed_entry_id', '=', record.account_move_id.id)], limit=1)
                if reverse_id:
                    record.write({
                        'reverse_account_move_id': reverse_id.id
                    })
            quantity_list = []
            avg_price_list = []
            move_ids = []
            stock_picking = self.env['stock.picking'].sudo().search([('id', '=', record.picking_list_id.id), ('picking_type_id', '=', record.stock_picking_type_id.id)])
            if not stock_picking:
                for lines in record.product_stock_move_lines:
                    quantity_list.append(lines.quantity)
                    avg_price_list.append(lines.avg_price)
                    move_ids.append((0, 0, {
                        'product_id': lines.product_id.id,
                        'description_picking': lines.product_id.name,
                        'name': lines.product_id.name,
                        'product_uom_qty': lines.quantity,
                        'location_dest_id': record.location_id.id,
                        'location_id': vendor_location_id,
                    }))
                move_vals = {
                    'partner_id': record.partner_id.id,
                    'picking_type_id': record.stock_picking_type_id.id,
                    'location_dest_id': record.location_id.id,
                    'location_id': vendor_location_id,
                    'scheduled_date': fields.Datetime.today(),
                    'origin': record.name,
                    'move_ids_without_package': move_ids,
                }
                picking_id = self.env['stock.picking'].sudo().create(move_vals)
                if picking_id:
                    record.write({
                        'picking_list_id': picking_id.id,
                    })
                    picking_id.button_validate()
            if not record.journal_id:
                raise UserError('Please Select Journal')
            quantity = sum(quantity_list)
            avg_price = sum(avg_price_list)
            amount = (quantity * avg_price)
            box_lines = [
                {
                    'account_id': record.debit_account_id.id,
                    'partner_id': record.partner_id.id,
                    'journal_id': record.journal_id.id,
                    'name': f'Item {record.name}',
                    'debit': amount,
                    'credit': 0.0,
                },
                {
                    'account_id': record.credit_account_id.id,
                    'partner_id': record.partner_id.id,
                    'journal_id': record.journal_id.id,
                    'name': f'Item {record.name}',
                    'debit': 0.0,
                    'credit': amount,
                }
            ]
            box_lines_tuples = [(0, 0, line) for line in box_lines]
            vals = {
                'ref': record.name,
                'partner_id': record.partner_id.id,
                'date': date.today(),
                'journal_id': record.journal_id.id,
                'line_ids': box_lines_tuples,
            }
            account_move = self.env['account.move'].sudo().create(vals)
            if account_move:
                account_move.action_post()
                record.write({
                    'account_move_list_id': account_move.id
                })
            record.write({
                'state': 'box_validate',
            })

    def action_product_box(self):
        for record in self:
            return {
                'name': _('Product Variants'),
                'view_mode': 'form',
                'view_id': self.env.ref('product.product_normal_form_view').id,
                'res_model': 'product.product',
                'context': "",
                'type': 'ir.actions.act_window',
                'res_id': record.product_id.id,
            }

    def action_operations_type_receipts(self):
        for record in self:
            return {
                'name': _('Receipts'),
                'view_mode': 'form',
                'view_id': self.env.ref('stock.view_picking_form').id,
                'res_model': 'stock.picking',
                'context': "",
                'type': 'ir.actions.act_window',
                'res_id': record.picking_id.id,
            }

    def action_product_box_list(self):
        for record in self:
            record.ensure_one()
            action = self.env["ir.actions.actions"]._for_xml_id('stock.stock_product_normal_action')
            action.update({
                'domain': [('id', 'in', record.product_stock_move_lines.mapped('product_id').ids)],
                'views': [[False, 'list'], [False, 'kanban'], [False, 'activity'], [False, 'form']],
                'context': dict(self.env.context)
            })
            return action

    def action_operations_type_receipts_list(self):
        for record in self:
            return {
                'name': _('Receipts'),
                'view_mode': 'form',
                'view_id': self.env.ref('stock.view_picking_form').id,
                'res_model': 'stock.picking',
                'context': "",
                'type': 'ir.actions.act_window',
                'res_id': record.picking_list_id.id,
            }

    def action_journal_entries(self):
        for record in self:
            return {
                'name': _('Journal Entries'),
                'view_mode': 'form',
                'view_id': self.env.ref('account.view_move_form').id,
                'res_model': 'account.move',
                'context': "{'move_type':'entry'}",
                'type': 'ir.actions.act_window',
                'res_id': record.account_move_id.id,
            }

    def action_reverse_journal_entries(self):
        for record in self:
            return {
                'name': _('Journal Entries'),
                'view_mode': 'form',
                'view_id': self.env.ref('account.view_move_form').id,
                'res_model': 'account.move',
                'context': "{'move_type':'entry'}",
                'type': 'ir.actions.act_window',
                'res_id': record.reverse_account_move_id.id,
            }

    def action_journal_entries_list(self):
        for record in self:
            return {
                'name': _('Journal Entries'),
                'view_mode': 'form',
                'view_id': self.env.ref('account.view_move_form').id,
                'res_model': 'account.move',
                'context': "{'move_type':'entry'}",
                'type': 'ir.actions.act_window',
                'res_id': record.account_move_list_id.id,
            }

    def action_draft(self):
        for record in self:
            record.write({
                'state': 'draft',
            })

