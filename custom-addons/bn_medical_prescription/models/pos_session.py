from odoo import _, models, Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.osv import expression

PRESCRIPTION_SEARCH_LIMIT = 50


class PosSession(models.Model):
    _inherit = 'pos.session'

    # ------------------------------------------------------------------
    # Prescription desk / billing counter
    # Cashiers have no rights on prescriptions and usually none on donee profiles,
    # so these run as superuser, gated on the counter of the session.
    # ------------------------------------------------------------------

    def _check_medical_counter(self, *roles):
        self.ensure_one()
        config = self.config_id
        if not config.is_medical_pos or config.medical_pos_role not in roles:
            raise AccessError(_("This action isn't available on %s.", config.name))
        # the session is given by id from the client: it must be one this user can see
        self.check_access_rule('read')

    def _medical_prescription(self, prescription_id):
        prescription = self.env['medical.prescription'].sudo().browse(int(prescription_id or 0)).exists()
        if not prescription or prescription.company_id != self.config_id.company_id:
            raise UserError(_("This prescription doesn't exist anymore."))
        return prescription

    def pos_approve_medical_prescription(self, vals):
        """Create the approved prescription of the patient from the order of the prescription desk"""
        self._check_medical_counter('prescription')

        partner = self.env['res.partner'].sudo().search(expression.AND([
            [('id', '=', int(vals.get('partner_id') or 0))],
            self.env['res.partner']._mh_patient_domain(),
        ]), limit=1)
        if not partner:
            raise ValidationError(_("Please select a registered patient."))

        lines = vals.get('lines') or []
        if not lines:
            raise ValidationError(_("Add the prescribed products first."))
        products = self.env['product.product'].browse({int(line['product_id']) for line in lines}).exists()

        line_commands = []
        for line in lines:
            product = products.filtered(lambda p: p.id == int(line['product_id']))
            if not product:
                raise ValidationError(_("A product of the prescription doesn't exist anymore."))
            qty = float(line.get('qty') or 0)
            if qty <= 0:
                raise ValidationError(_("The quantity of %s must be positive.", product.display_name))
            line_commands.append(Command.create({
                'product_id': product.id,
                'qty': qty,
                'price_unit': float(line.get('price_unit') or 0),
                'discount': float(line.get('discount') or 0),
                'note': (line.get('note') or '').strip() or False,
            }))

        prescription = self.env['medical.prescription'].sudo().create({
            'partner_id': partner.id,
            'doctor_name': (vals.get('doctor_name') or '').strip() or False,
            'note': (vals.get('note') or '').strip() or False,
            'company_id': self.config_id.company_id.id,
            'desk_config_id': self.config_id.id,
            'pos_session_id': self.id,
            'pos_config_id': self.config_id.id,
            'pos_cashier_id': self.env.user.id,
            'line_ids': line_commands,
        })
        prescription.action_approve()
        return prescription._pos_data(self)[0]

    def pos_get_medical_prescriptions(self, partner_id=False, term=''):
        """Approved prescriptions waiting for their bill, of the patient or matching the term"""
        self._check_medical_counter('prescription', 'billing')
        domain = [('state', '=', 'approved'), ('company_id', '=', self.config_id.company_id.id)]
        if partner_id:
            domain.append(('partner_id', '=', int(partner_id)))
        term = (term or '').strip()
        if term:
            domain = expression.AND([domain, expression.OR([
                [('name', 'ilike', term)],
                [('partner_id.name', 'ilike', term)],
                [('partner_id.mobile', 'ilike', term)],
                [('partner_id.cnic_no', 'ilike', term)],
                [('partner_id.primary_registration_id', 'ilike', term)],
            ])])
        prescriptions = self.env['medical.prescription'].sudo().search(
            domain, limit=PRESCRIPTION_SEARCH_LIMIT, order='approved_date desc, id desc')
        return prescriptions._pos_data(self)

    def pos_cancel_medical_prescription(self, prescription_id):
        """The prescription desk takes back a prescription that isn't billed yet"""
        self._check_medical_counter('prescription')
        prescription = self._medical_prescription(prescription_id)
        if prescription.state != 'approved':
            raise UserError(_("Only an approved prescription that isn't billed yet can be cancelled."))
        prescription.action_cancel()
        prescription.message_post(body=_("Cancelled from %s.", self.config_id.name))
        return True

    def pos_check_medical_prescription(self, prescription_id, partner_id):
        """Before the payment: the prescription is still waiting for its bill, for this patient"""
        self._check_medical_counter('billing')
        prescription = self._medical_prescription(prescription_id)
        if prescription.state != 'approved':
            state = dict(prescription._fields['state']._description_selection(self.env))[prescription.state]
            raise UserError(_("Prescription %(name)s is %(state)s, it can't be billed.", name=prescription.name, state=state))
        if prescription.partner_id.id != int(partner_id or 0):
            raise UserError(_("Prescription %(name)s is for %(patient)s, please select this patient.",
                              name=prescription.name, patient=prescription.partner_id.name))
        return True
