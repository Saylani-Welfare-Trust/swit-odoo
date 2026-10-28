from collections import defaultdict
from datetime import timedelta

from odoo import SUPERUSER_ID, models, fields, api
from odoo.exceptions import UserError
from odoo.tools import float_compare

EDIT_AMOUNT_GROUP = 'bn_rider_shift.group_edit_rider_collection'

# How far the POS order time may be from the moment the collection was marked Paid:
# both happen on the same click, the POS order time comes from the browser clock.
POS_MATCH_WINDOW = timedelta(minutes=10)


day_selection = [
    ('mon', 'Monday'),
    ('tue', 'Tuesday'),
    ('wed', 'Wednesday'),
    ('thu', 'Thursday'),
    ('fri', 'Friday'),
    ('sat', 'Saturday'),
    ('sun', 'Sunday'),
]

state_selection = [
    ('donation_not_collected', 'Donation not collected'),
    ('donation_collected', 'Donation collected'),
    ('donation_submit', 'Donation submit'),
    ('pending', 'Pending'),
    ('paid', 'Paid')
]


class RiderCollection(models.Model):
    _name = 'rider.collection'
    _description = "Rider Collection"
    _rec_name = "shop_name"

    counterfeit_note_ids = fields.Many2many(
        'counterfeit.notes',
        'rider_collection_counterfeit_rel',
        'collection_id',
        'note_id',
        string='Counterfeit Notes'
    )

    rider_id = fields.Many2one('hr.employee', string="Rider")
    donation_box_registration_installation_id = fields.Many2one('donation.box.registration.installation', string="Donation Box")

    shop_name = fields.Char(related='donation_box_registration_installation_id.shop_name', string="Shop Name", store=True)
    contact_person = fields.Char(related='donation_box_registration_installation_id.contact_person', string="Contact Person", store=True)
    contact_number = fields.Char(related='donation_box_registration_installation_id.contact_no', string="Contact Number", store=True)
    box_location = fields.Char(related='donation_box_registration_installation_id.location', string="Box Location", store=True)

    lot_id = fields.Many2one(related='donation_box_registration_installation_id.lot_id', string="Box No.", store=True)
    key_bunch_id = fields.Many2one(related='donation_box_registration_installation_id.key_bunch_id', string="Key Bunch", store=True)
    sub_zone_id = fields.Many2one(related='donation_box_registration_installation_id.sub_zone_id', string="Sub Zone", store=True)

    day = fields.Selection(selection=day_selection, string="Day", default='mon')
    state = fields.Selection(selection=state_selection, string="Status", default='donation_not_collected')

    is_complain_generated = fields.Boolean('Is Complain Generated', default=False)
    
    date = fields.Date("Date")

    submission_time = fields.Date('Submission Date')

    amount = fields.Float('Amount')
    foreign_notes = fields.Float('Foreign Currency')
    counterfeit_notes = fields.Float('Counterfeit Notes')

    remarks = fields.Text('Remarks')

    # Set when the POS order that paid this collection reaches the server (pos_order.py).
    pos_order_id = fields.Many2one('pos.order', string="POS Order", copy=False, readonly=True)
    dn_number = fields.Char('DN Number', copy=False, readonly=True)
    foreign_currency_line_ids = fields.Many2many(
        'foreign.currency',
        'rider_collection_foreign_currency_rel',
        'collection_id',
        'foreign_currency_id',
        string='Foreign Currency Lines'
    )

    is_fcb = fields.Boolean('Is FCB', compute='_compute_is_fcb')
    
    def _compute_is_fcb(self):
        for record in self:
            record.is_fcb = record.remarks == 'FCB'

    def write(self, vals):
        # 'amount' / 'counterfeit_notes' must only be editable by users in the
        # "Edit Amount / Notes" group - the view groups=/readonly= attributes alone
        # are cosmetic and can be bypassed from any screen that doesn't apply them
        # (e.g. the form view previously had no restriction at all).
        if not self.env.su and ('amount' in vals or 'counterfeit_notes' in vals):
            if not self.env.user.has_group(EDIT_AMOUNT_GROUP):
                raise UserError(
                    "You are not allowed to edit the Amount / Counterfeit Notes of a "
                    "Rider Collection. Required access group: Rider Collection / Edit "
                    "Amount / Notes."
                )
        return super().write(vals)
    
    def action_mark_cfb_paid(self):
        """Mark all linked counterfeit notes as paid"""
        for collection in self:
            if collection.remarks == 'CFB' and collection.counterfeit_note_ids:
                collection.counterfeit_note_ids.write({'state': 'payment_received'})
                collection.state = 'paid'
        return True

    def action_fill_dn_number_from_pos(self):
        """Server action "Find DN # from POS": link Paid collections paid before the POS
        order was kept on them. Only a collection with exactly one matching POS order
        is filled; the others are listed."""
        product_name = self.env.company.donation_box_product
        if not product_name:
            raise UserError("Please set the Donation Box product on the company first.")

        todo = self.filtered(lambda c: c.state == 'paid' and not c.pos_order_id).sorted('id')
        total = len(todo)
        used_order_ids = set(self.sudo().search([('pos_order_id', '!=', False)]).pos_order_id.ids)
        # Matches by the customer the POS sets first, then by cashier and time. An order
        # is only taken when a single collection points to it, and passes are repeated:
        # an order taken by one collection is no candidate for the others any more.
        for by_moment in (False, True):
            progress = True
            while progress and todo:
                progress = False
                claims = defaultdict(lambda: self.browse())
                for collection in todo:
                    order = collection._bn_find_paying_pos_order(product_name, used_order_ids, by_moment)
                    if order:
                        claims[order] |= collection
                for order, collections in claims.items():
                    if len(collections) == 1:
                        order._bn_link_rider_collection(collections.id)
                        used_order_ids.add(order.id)
                        todo -= collections
                        progress = True
        unmatched = todo

        message = "DN # filled for %s of %s Paid collection(s) without one." % (total - len(unmatched), total)
        if unmatched:
            names = ', '.join('%s (%s)' % (c.shop_name or '-', c.lot_id.name or '-') for c in unmatched[:20].sudo())
            more = ' and %s more' % (len(unmatched) - 20) if len(unmatched) > 20 else ''
            message += " No single matching POS order for: %s%s." % (names, more)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': "Find DN # from POS",
                'message': message,
                'type': 'warning' if unmatched else 'success',
                'sticky': bool(unmatched),
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    def _bn_find_paying_pos_order(self, product_name, used_order_ids, by_moment=False):
        """The POS order that paid this collection, or an empty recordset when it is not
        sure. Candidates: a paid order with a Donation Box line of the same amount, not
        linked to another collection, between this collection's submission and the next
        collection of the same box. One of them is taken only when it is the only one
        with the customer the POS sets or, with ``by_moment``, the only one by the
        cashier close to the moment the collection was marked Paid."""
        self.ensure_one()
        registration = self.donation_box_registration_installation_id
        start = self.submission_time or self.date
        domain = [
            ('product_id.name', '=', product_name),
            ('qty', '>', 0),
            ('order_id.state', 'in', ('paid', 'done', 'invoiced')),
            ('order_id', 'not in', list(used_order_ids)),
        ]
        if start:
            # a day early: date_order is UTC, the submission date is local
            domain.append(('order_id.date_order', '>=', fields.Datetime.to_datetime(start) - timedelta(days=1)))
        next_collection = self.search([
            ('donation_box_registration_installation_id', '=', registration.id),
            ('date', '>', self.date), ('id', '!=', self.id),
        ], order='date', limit=1) if registration and self.date else self.browse()
        end = next_collection.submission_time or next_collection.date
        if end:
            domain.append(('order_id.date_order', '<', fields.Datetime.to_datetime(end) + timedelta(days=1)))
        lines = self.env['pos.order.line'].sudo().search(domain)
        orders = lines.filtered(
            lambda l: float_compare(l.price_subtotal_incl, self.amount, precision_digits=2) == 0).order_id

        customer = self._bn_pos_customer()
        by_customer = orders.filtered(lambda o: o.partner_id == customer) if customer else orders.browse()
        if not by_moment:
            return by_customer if len(by_customer) == 1 else orders.browse()

        cashier, paid_at = self._bn_paid_moment()
        if not (cashier and paid_at):
            return orders.browse()
        matched = (by_customer or orders).filtered(
            lambda o: o.user_id == cashier and abs(o.date_order - paid_at) <= POS_MATCH_WINDOW)
        return matched if len(matched) == 1 else orders.browse()

    def _bn_pos_customer(self):
        """Customer the POS puts on the order (see key.issuance.set_donation_amount)."""
        self.ensure_one()
        Partner = self.env['res.partner'].sudo()
        if self.remarks == 'CFB':
            return Partner.search([('name', 'ilike', 'Counterfeit')], limit=1)
        if self.remarks == 'FCB':
            return Partner.search([('name', 'ilike', 'Foreign Currency Donor')], limit=1)
        return self.donation_box_registration_installation_id.donor_id

    def _bn_paid_moment(self):
        """(cashier, time) the POS marked this collection Paid. Taken from the chatter of
        its key issuance (the POS sets it to Donation Received, or Returned for CFB / FCB),
        else from the collection's last write unless the system made it (an upgrade
        that fills a new stored field rewrites every record)."""
        self.ensure_one()
        Issuance = self.env['key.issuance'].sudo()
        issuance = Issuance.search([('rider_collection_id', '=', self.id)], limit=1)
        if not issuance and self.lot_id and self.date:
            issuance = Issuance.search([('key_id.lot_id', '=', self.lot_id.id), ('issue_date', '=', self.date)], limit=1)
        if issuance:
            state = 'returned' if self.remarks in ('CFB', 'FCB') else 'donation_receive'
            label = dict(Issuance._fields['state'].selection)[state]
            tracking = self.env['mail.tracking.value'].sudo().search([
                ('mail_message_id.model', '=', 'key.issuance'),
                ('mail_message_id.res_id', '=', issuance.id),
                ('field_id.name', '=', 'state'),
                ('new_value_char', '=', label),
            ], order='id desc', limit=1)
            message = tracking.mail_message_id
            user = message.author_id.user_ids[:1]
            if user:
                return user, message.date
        if self.write_uid and self.write_uid.id != SUPERUSER_ID:
            return self.write_uid, self.write_date
        return self.env['res.users'], False

    @api.model
    def get_rider_collection(self):
        collection_ids = self.sudo().search([('amount', '!=', 0), ('state', '=', 'donation_submit')])

        if not collection_ids:
            return {
                "status": "error",
                "body": f"No donation collections were found for today {fields.Date.today().strftime('%d-%m-%Y')}."
            }

        return {
            "status": "success",
            'collection_ids': [{
                'id': collection.id,
                'day': collection.day,
                'date': collection.date,
                'lot_id': collection.lot_id.id if collection.lot_id else False,
                'box_no': collection.lot_id.name if collection.lot_id else '',
                'shop_name': collection.shop_name,
                'contact_person': collection.contact_person,
                'contact_number': collection.contact_number,
                'box_location': collection.box_location,
                'amount': collection.amount,
                'rider_id': collection.rider_id.id
            } for collection in collection_ids],
            'rider_ids': [
                {'id': rider.id, 'name': rider.name}
                for rider in collection_ids.mapped('rider_id')
            ]
        }
    