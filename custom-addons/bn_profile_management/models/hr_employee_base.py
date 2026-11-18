from odoo import models, _
from odoo.exceptions import UserError


class HrEmployeeBase(models.AbstractModel):
    _inherit = 'hr.employee.base'


    def _create_work_contacts(self):
        if any(employee.work_contact_id for employee in self):
            raise UserError(_('Some employee already have a work contact'))

        PartnerCategory = self.env['res.partner.category']
        # Ensure the "Employee, Individual, and on scenario Donor / Donee" tag exists
        employee_tag = PartnerCategory.search([('name', '=', 'Employee')], limit=1)
        individual_tag = PartnerCategory.search([('name', '=', 'Individual')], limit=1)

        Partner = self.env['res.partner']
        work_contacts = []
        for employee in self:
            tags = PartnerCategory.search([('name', 'in', employee.category_ids.mapped('name'))]) \
                | employee_tag | individual_tag
            mobile = Partner._normalize_mobile(employee.mobile_phone) if employee.mobile_phone else False
            # one contact per person: an employee who already is a contact
            # (donor, donee ...) keeps that contact, with the Employee tag
            work_contacts.append(Partner._find_or_create_person({
                'email': employee.work_email,
                'mobile': mobile if mobile and len(mobile) == 10 and mobile.isdigit() else False,
                'name': employee.name,
                'image_1920': employee.image_1920,
                'company_id': employee.company_id.id,
            }, tags=tags))

        for employee, work_contact in zip(self, work_contacts):
            employee.work_contact_id = work_contact