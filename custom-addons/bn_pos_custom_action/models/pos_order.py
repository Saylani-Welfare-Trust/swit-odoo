from odoo import api, fields, models


class POSOrder(models.Model):
    _inherit = 'pos.order'


    source_document = fields.Char('Source Document')
    
    pos_cheque_order_id = fields.Integer('POS Cheque Order Id')
    
    qurbani = fields.Boolean('Qurbani', default=False)
    receive_voucher = fields.Boolean('Receive Voucher', default=False)

    pos_order_seq = fields.Char('Custom POS Order Seq')

    def _branch(self):
        """The Branch the order is tagged with: its session's (the shop's)."""
        self.ensure_one()
        return self.session_id.analytic_account_id or self.config_id.analytic_account_id

    def _branch_code(self):
        """Branch code of the DN # and order references: the shop's branch."""
        return self._branch().code or 'UNK'


    def _order_fields(self, ui_order):
        """To get the value of field in pos session to pos order"""
        res = super(POSOrder, self)._order_fields(ui_order)

        res['pos_cheque_order_id'] = ui_order.get('pos_cheque_order_id') or False
        res['source_document'] = ui_order.get('source_document') or False
        res['receive_voucher'] = ui_order.get('receive_voucher') or False
        # pos_order_seq is given by the server (_assign_pos_order_seq), never taken from the POS
        res['qurbani'] = ui_order.get('qurbani') or False

        return res

    # ------------------------------------------------------------------
    # Receipt number (pos_order_seq), the last part of the DN #
    # <branch code>-C<counter>-<year>-<pos_order_seq>: one sequence per
    # Branch and counter, restarting at 1 every year. Given by the server
    # when the order is saved, so two POS screens (or browsers) of the same
    # counter can never print the same number.
    # ------------------------------------------------------------------
    @api.model
    def _process_order(self, order, draft, existing_order):
        order_id = super()._process_order(order, draft, existing_order)
        if not draft:
            self.browse(order_id)._assign_pos_order_seq()
        return order_id

    @api.model
    def create_from_ui(self, orders, draft=False):
        """Give the POS the receipt numbers, for the receipt it prints."""
        result = super().create_from_ui(orders, draft=draft)
        seqs = dict(self.sudo().browse([r['id'] for r in result]).mapped(lambda o: (o.id, o.pos_order_seq)))
        for res in result:
            res['pos_order_seq'] = seqs.get(res['id']) or False
        return result

    def _export_for_ui(self, order):
        """Orders loaded back in the POS (reprint) keep their receipt number."""
        result = super()._export_for_ui(order)
        result['pos_order_seq'] = order.pos_order_seq or False
        return result

    def _pos_order_seq_date(self):
        """The day of the order in the user's timezone: its year is the DN # year."""
        self.ensure_one()
        return fields.Datetime.context_timestamp(self, self.date_order or fields.Datetime.now()).date()

    def _assign_pos_order_seq(self):
        for order in self.sudo():
            if order.pos_order_seq:
                continue
            seq_date = order._pos_order_seq_date()
            sequence = order._pos_order_sequence(seq_date)
            order.pos_order_seq = sequence.next_by_id(sequence_date=seq_date)

    def _pos_order_sequence(self, seq_date):
        """The sequence of the order's Branch and counter, with this year's range.

        Locked for the transaction: orders of the same counter are numbered one
        after the other, so a number is never given twice."""
        self.ensure_one()
        branch = self._branch()
        counter = self.config_id.counter or 0
        code = 'bn_pos_order_seq.%s.%s' % (branch.id or 0, counter)
        self.env.cr.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [code])
        Sequence = self.env['ir.sequence'].sudo()
        sequence = Sequence.search([('code', '=', code)], limit=1)
        if not sequence:
            sequence = Sequence.create({
                'name': 'POS Receipt No. %s-C%s' % (branch.code or 'UNK', counter),
                'code': code,
                'implementation': 'no_gap',
                'use_date_range': True,
                'padding': 0,
                'number_increment': 1,
                'company_id': False,
            })
        year_start, year_end = seq_date.replace(month=1, day=1), seq_date.replace(month=12, day=31)
        DateRange = self.env['ir.sequence.date_range'].sudo()
        if not DateRange.search([('sequence_id', '=', sequence.id),
                                 ('date_from', '<=', seq_date), ('date_to', '>=', seq_date)], limit=1):
            # A new year starts at 1; the first year continues after the numbers
            # the POS screens already gave this year (before the server did).
            DateRange.create({
                'sequence_id': sequence.id, 'date_from': year_start, 'date_to': year_end,
                # number_next_actual, not number_next: on create its default (1)
                # would be written over number_next by its inverse
                'number_next_actual': self._last_pos_order_seq(branch, counter, year_start, year_end) + 1,
            })
        return sequence

    def _last_pos_order_seq(self, branch, counter, date_from, date_to):
        """Highest receipt number already used by the Branch and counter in the year."""
        tz = self.env.user.tz or 'UTC'
        self.env.cr.execute("""
            SELECT MAX(o.pos_order_seq::bigint)
              FROM pos_order o
              JOIN pos_session s ON s.id = o.session_id
              JOIN pos_config c ON c.id = s.config_id
             WHERE o.pos_order_seq ~ '^[0-9]{1,15}$'
               AND COALESCE(c.counter, 0) = %s
               AND COALESCE(s.analytic_account_id, c.analytic_account_id, 0) = %s
               AND (o.date_order AT TIME ZONE 'UTC' AT TIME ZONE %s)::date BETWEEN %s AND %s
        """, [counter, branch.id or 0, tz, date_from, date_to])
        return self.env.cr.fetchone()[0] or 0

