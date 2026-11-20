from odoo.tests import TransactionCase, tagged

from odoo.addons.bn_medical_equipment.models.medical_equipment import _equipment_donee_domain


@tagged('post_install', '-at_install')
class TestEquipmentDoneeDomain(TransactionCase):
    """The Donee picker of Medical Equipment offers registered donees tagged
    Medical Equipment only (not the "Medical" patients of the Medical POS)."""

    def test_only_medical_equipment_donees(self):
        ref = lambda name: self.env.ref('bn_profile_management.%s_partner_category' % name)
        Partner = self.env['res.partner']

        def partner(name, *tags):
            return Partner.create({'name': name, 'category_id': [(6, 0, [ref(t).id for t in tags])]})
        equipment = partner('ME Donee', 'donee', 'medical')
        patient = partner('ME Patient', 'donee', 'medical_patient')
        welfare = partner('ME Welfare', 'donee', 'welfare')
        domain = _equipment_donee_domain(self.env['medical.equipment'])
        self.assertIn(('state', '=', 'register'), domain)
        # the tag part (registration is tested by bn_profile_management)
        tags = [leaf for leaf in domain if leaf[0] != 'state']
        found = Partner.search(tags + [('id', 'in', (equipment | patient | welfare).ids)])
        self.assertEqual(found, equipment)
