from odoo import models, fields, api


class ClosingScreen(models.TransientModel):
    _name = 'wizard.closing.screen'

    name = fields.Char(string='Name')
    pos_session = fields.Many2one('pos.session', string="Session", default=lambda self: self._get_session())

    line_id = fields.One2many('wizard.closing.screen.line', 'master_id', string='line',
                              default=lambda self: self._get_lines())

    def _get_session(self):
        data = self.env['pos.session'].search([('state', '=', 'opened')], limit=1)
        return data.id or False

    def _get_lines(self):
        lines = []
        session = self.env['pos.session'].search([('state', '=', 'opened')], limit=1)
        # orders = session.order_ids
        # for ord in orders:
        #     print(ord.lines.product_id.pos_categ_ids)

        if session:
            # Get payments related to this session
            payments = self.env['pos.payment'].search([('session_id', '=', session.id)])

            # Group by payment method and sum amounts
            payment_dict = {}
            for payment in payments:
                payment_method = payment.payment_method_id
                # if payment.pos_order_id.id == 50:
                #     continue
                categ_id = payment.pos_order_id.lines.product_id.mapped('pos_categ_ids.parent_id')
                # print(payment.pos_order_id, categ_id)
                # categ_id = self.env['pos.category'].browse(payment.pos_order_id.category_id)
                if payment_method in payment_dict:
                    payment_dict[payment_method] += (payment.amount, categ_id.id)
                else:
                    payment_dict[payment_method] = (payment.amount, categ_id.id)
            # Create line items
            for payment_method, total_amount in payment_dict.items():
                lines.append((0, 0, {
                    'payment_method': payment_method.id,
                    'amount': total_amount[0],
                    'pos_category': total_amount[1],
                }))

        return lines

    def action_save(self):
        if self.line_id:
            data = {
                "name": self.name,
                "pos_session": self.pos_session.id,
                "state": "draft"
            }
            obj = self.env['closing.screen'].create(data)
        for rec in self.line_id:
            self.env['closing.screen.line'].create({
                "master_id": obj.id,
                "payment_method": rec.payment_method.id,
                "amount": rec.amount,
                "deposit_slip": rec.deposit_slip,
                "pos_category": rec.pos_category.id
            })


class ClosingScreenLine(models.TransientModel):
    _name = 'wizard.closing.screen.line'

    master_id = fields.Many2one('wizard.closing.screen', string='Master')
    payment_method = fields.Many2one('pos.payment.method')
    amount = fields.Float(string='Amount')
    deposit_slip = fields.Integer(string='Deposite Slip Number')
    pos_category = fields.Many2one('pos.category', string='Category')