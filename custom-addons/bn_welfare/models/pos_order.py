from odoo import models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _bn_pos_documents(self, extra_data):
        res = super()._bn_pos_documents(extra_data)
        Line, Recurring = self.env['welfare.line'], self.env['welfare.recurring.line']
        wf = extra_data.get('welfare') or {}
        ids = [line.get('id') for line in (wf.get('recurring_line_ids') if wf.get('is_recurring') else wf.get('welfare_line_ids')) or []
               if isinstance(line, dict) and line.get('id')]
        res.append((Recurring if wf.get('is_recurring') else Line).browse(ids).exists())
        ret = extra_data.get('welfare_return') or {}
        ret_ids = [line.get('id') for line in ret.get('line_ids') or [] if isinstance(line, dict) and line.get('id')]
        res.append((Recurring if ret.get('return_type') == 'recurring' else Line).browse(ret_ids).exists())
        return res
