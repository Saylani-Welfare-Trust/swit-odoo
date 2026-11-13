from odoo import fields, models, tools


class MedicalPatient(models.Model):
    """Patients: registered donees tagged Medical (Donee + Medical tags, state Registered).

    A read-only view on the partners, so the Medical & Health users see the patients even when
    the Profile Management rules hide the donees from them (edit_donor_rule).
    The profile itself stays in Profile Management.
    """
    _name = 'mh.patient'
    _description = 'Patient'
    _auto = False
    _order = 'id desc'

    partner_id = fields.Many2one('res.partner', 'Profile', readonly=True)
    name = fields.Char('Name', readonly=True)
    registration_id = fields.Char('Registration No.', readonly=True)
    cnic_no = fields.Char('CNIC No.', readonly=True)
    mobile = fields.Char('Mobile No.', readonly=True)
    date_of_birth = fields.Date('Date of Birth', readonly=True)
    registered_on = fields.Datetime('Registered On', readonly=True)
    image_128 = fields.Image(related='partner_id.image_128', string='Photo')
    # the photo widget keys its cache on it
    write_date = fields.Datetime('Last Updated on', readonly=True)
    age = fields.Integer('Age', compute='_compute_age')

    def _compute_age(self):
        today = fields.Date.context_today(self)
        for patient in self:
            dob = patient.date_of_birth
            patient.age = (today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))) if dob else 0

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT p.id AS id,
                       p.id AS partner_id,
                       p.name AS name,
                       p.primary_registration_id AS registration_id,
                       p.cnic_no AS cnic_no,
                       p.mobile AS mobile,
                       p.date_of_birth AS date_of_birth,
                       p.create_date AS registered_on,
                       p.write_date AS write_date
                  FROM res_partner p
                 WHERE p.active
                   AND p.state = 'register'
                   AND EXISTS (
                        SELECT 1
                          FROM res_partner_res_partner_category_rel rel
                          JOIN ir_model_data imd ON imd.model = 'res.partner.category' AND imd.res_id = rel.category_id
                         WHERE rel.partner_id = p.id
                           AND imd.module = 'bn_profile_management' AND imd.name = 'donee_partner_category')
                   AND EXISTS (
                        SELECT 1
                          FROM res_partner_res_partner_category_rel rel
                          JOIN ir_model_data imd ON imd.model = 'res.partner.category' AND imd.res_id = rel.category_id
                         WHERE rel.partner_id = p.id
                           AND imd.module = 'bn_profile_management' AND imd.name = 'medical_partner_category')
            )
        """)
