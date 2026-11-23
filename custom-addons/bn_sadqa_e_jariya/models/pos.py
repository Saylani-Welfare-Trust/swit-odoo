from odoo import models, api


class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def _order_fields(self, ui_order):
        vals = super()._order_fields(ui_order)
        if (ui_order.get('extra_data') or {}).get('sadqa_jariya'):
            vals['is_non_donation_receipt'] = True
        return vals

    def _pos_documents(self, extra_data):
        """Sadqa e Jariya lines disbursed by this order (extra_data['sadqa_jariya']):
        they get its POS order, session, POS and cashier."""
        res = super()._pos_documents(extra_data)
        data = extra_data.get('sadqa_jariya') or {}
        model = data.get('line_model')
        if model in ('sadqa.jariya.line', 'sadqa.jariya.recurring.line'):
            ids = [line.get('id') for line in data.get('line_ids') or [] if isinstance(line, dict) and line.get('id')]
            res.append(self.env[model].browse(ids).exists())
        return res


class SadqaJariyaLinePosLink(models.Model):
    _name = 'sadqa.jariya.line'
    _inherit = ['pos.link.mixin', 'sadqa.jariya.line']


class SadqaJariyaRecurringLinePosLink(models.Model):
    _name = 'sadqa.jariya.recurring.line'
    _inherit = ['pos.link.mixin', 'sadqa.jariya.recurring.line']
