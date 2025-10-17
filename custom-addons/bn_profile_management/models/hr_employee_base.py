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

        work_contacts = self.env['res.partner'].create([{
            'email': employee.work_email,
            'mobile': employee.mobile_phone,
            'name': employee.name,
            'image_1920': employee.image_1920,
            'company_id': employee.company_id.id,
            'category_id': [(6, 0, list(set(
                PartnerCategory.search([('name', 'in', employee.category_ids.mapped('name'))]).ids
                + [employee_tag.id, individual_tag.id]
            )))]
        } for employee in self])

        for employee, work_contact in zip(self, work_contacts):
            employee.work_contact_id = work_contact