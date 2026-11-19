from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPosOrderSeq(TransactionCase):
    """Receipt numbers (pos_order_seq) are given by the server: one sequence
    per Branch and counter, never twice the same number, restarting every year."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        plan = cls.env['account.analytic.plan'].create({'name': 'Seq Locations'})
        cls.branch = cls.env['account.analytic.account'].create(
            {'name': 'Seq Branch', 'code': 'SQB', 'plan_id': plan.id})

    def _session(self, name, counter):
        config = self.env['pos.config'].create(
            {'name': name, 'counter': counter, 'analytic_account_id': self.branch.id})
        return self.env['pos.session'].create({'config_id': config.id, 'user_id': self.env.uid})

    def _order(self, session, date, seq=False):
        return self.env['pos.order'].create({
            'session_id': session.id, 'date_order': date, 'pos_order_seq': seq,
            'amount_tax': 0, 'amount_total': 0, 'amount_paid': 0, 'amount_return': 0})

    def _numbers(self, orders):
        orders._assign_pos_order_seq()
        return [o.pos_order_seq for o in orders]

    def test_counter_numbers_are_unique(self):
        # two POS screens of the same Branch and counter share one sequence
        screen_1, screen_2 = self._session('Seq C1 A', 1), self._session('Seq C1 B', 1)
        orders = (self._order(screen_1, '2026-03-01 08:00:00') | self._order(screen_2, '2026-03-01 08:00:00')
                  | self._order(screen_1, '2026-03-02 08:00:00'))
        self.assertEqual(self._numbers(orders), ['1', '2', '3'])
        # a number once given is kept
        self.assertEqual(self._numbers(orders), ['1', '2', '3'])

    def test_each_counter_has_its_own_numbers(self):
        c1, c2 = self._session('Seq C1', 1), self._session('Seq C2', 2)
        orders = self._order(c1, '2026-03-01 08:00:00') | self._order(c2, '2026-03-01 08:00:00')
        self.assertEqual(self._numbers(orders), ['1', '1'])

    def test_new_year_restarts_at_one(self):
        session = self._session('Seq Year', 3)
        orders = (self._order(session, '2026-12-30 08:00:00') | self._order(session, '2026-12-30 09:00:00')
                  | self._order(session, '2027-01-02 08:00:00'))
        self.assertEqual(self._numbers(orders), ['1', '2', '1'])

    def test_continues_after_numbers_already_printed(self):
        """The year the server starts numbering, it goes on after the numbers
        the POS screens already printed that year."""
        session = self._session('Seq Old', 4)
        self._order(session, '2026-02-01 08:00:00', seq='40')
        self._order(session, '2025-06-01 08:00:00', seq='90')  # another year: not counted
        self.assertEqual(self._numbers(self._order(session, '2026-03-01 08:00:00')), ['41'])
