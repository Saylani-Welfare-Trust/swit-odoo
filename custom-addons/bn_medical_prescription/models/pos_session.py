from odoo import _, models
from odoo.exceptions import AccessError, UserError
from odoo.osv import expression

PRESCRIPTION_SEARCH_LIMIT = 50


class PosSession(models.Model):
    _inherit = 'pos.session'

    # ------------------------------------------------------------------
    # Medical & Health counter
    # Cashiers have no rights on prescriptions and usually none on donee profiles,
    # so these run as superuser, gated on the counter of the session.
    # ------------------------------------------------------------------

    def _check_medical_counter(self):
        self.ensure_one()
        config = self.config_id
        if not config.is_medical_pos:
            raise AccessError(_("This action isn't available on %s.", config.name))
        # the session is given by id from the client: it must be one this user can see
        self.check_access_rule('read')

    def _medical_prescription(self, prescription_id):
        prescription = self.env['medical.prescription'].sudo().browse(int(prescription_id or 0)).exists()
        if not prescription or prescription.company_id != self.config_id.company_id:
            raise UserError(_("This prescription doesn't exist anymore."))
        return prescription

    def pos_get_medical_doctors(self, product_ids):
        """The doctors listed in Master Setup on all the products selected on the order"""
        self._check_medical_counter()
        products = self.env['product.product'].sudo().browse([int(pid) for pid in product_ids or []]).exists()
        domain = ['|', ('company_id', '=', False), ('company_id', '=', self.config_id.company_id.id)]
        domain += [('product_ids', 'in', product.ids) for product in products]
        doctors = self.env['medical.doctor'].sudo().search(domain) if products else self.env['medical.doctor']
        return [{'id': doctor.id, 'name': doctor.name} for doctor in doctors]

    def pos_get_till_prescription(self, order_id):
        """The number of the draft prescription made by a paid till, printed on it"""
        self._check_medical_counter()
        return self.env['medical.prescription'].sudo().search([
            ('intake_order_id', '=', int(order_id or 0)),
            ('company_id', '=', self.config_id.company_id.id),
        ], limit=1).name or False

    def pos_get_medical_prescriptions(self, partner_id=False, term=''):
        """Approved prescriptions waiting for their bill, of the patient or matching the term"""
        self._check_medical_counter()
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

    def pos_check_medical_prescription(self, prescription_id, partner_id):
        """Before the payment: the prescription is still waiting for its bill, for this patient"""
        self._check_medical_counter()
        prescription = self._medical_prescription(prescription_id)
        if prescription.state != 'approved':
            state = dict(prescription._fields['state']._description_selection(self.env))[prescription.state]
            raise UserError(_("Prescription %(name)s is %(state)s, it can't be billed.", name=prescription.name, state=state))
        if prescription.partner_id.id != int(partner_id or 0):
            raise UserError(_("Prescription %(name)s is for %(patient)s, please select this patient.",
                              name=prescription.name, patient=prescription.partner_id.name))
        return True
