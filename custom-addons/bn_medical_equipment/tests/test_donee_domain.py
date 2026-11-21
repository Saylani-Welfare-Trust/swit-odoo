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


@tagged('post_install', '-at_install')
class TestEquipmentLotsOnHand(TransactionCase):
    """A Medical Equipment line offers the serials on hand in the location the
    equipment is shipped from, not those of other locations."""

    def test_lots_of_the_source_location_only(self):
        product = self.env['product.product'].create({
            'name': 'ME Wheelchair', 'detailed_type': 'product', 'tracking': 'serial'})
        Location = self.env['stock.location']
        source = Location.create({'name': 'ME Source', 'usage': 'internal'})
        other = Location.create({'name': 'ME Other', 'usage': 'internal'})
        Lot = self.env['stock.lot']
        here = Lot.create({'name': 'ME-001', 'product_id': product.id, 'company_id': self.env.company.id})
        there = Lot.create({'name': 'ME-002', 'product_id': product.id, 'company_id': self.env.company.id})
        Quant = self.env['stock.quant']
        Quant._update_available_quantity(product, source, 1, lot_id=here)
        Quant._update_available_quantity(product, other, 1, lot_id=there)
        domain = self.env['medical.equipment.line']._lots_on_hand_domain(product, source)
        self.assertEqual(Lot.search(domain), here)
        here.lot_consume = True
        self.assertFalse(Lot.search(domain), 'a serial taken by another application is not offered')
