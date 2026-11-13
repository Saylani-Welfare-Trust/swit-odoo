# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPartnerTags(TransactionCase):

    def test_tag_domain(self):
        Partner = self.env['res.partner']
        donee = self.env.ref('bn_profile_management.donee_partner_category')
        medical = self.env.ref('bn_profile_management.medical_partner_category')
        vendor = self.env.ref('bn_profile_management.vendor_partner_category')
        patient = Partner.create({'name': 'Tag Patient', 'category_id': [(6, 0, (donee | medical).ids)]})
        donee_only = Partner.create({'name': 'Tag Donee', 'category_id': [(6, 0, donee.ids)]})
        supplier = Partner.create({'name': 'Tag Vendor', 'category_id': [(6, 0, vendor.ids)]})
        found = Partner.search(Partner._tag_domain('donee', 'medical'))
        self.assertIn(patient, found)
        self.assertNotIn(donee_only, found, 'every tag is required')
        self.assertNotIn(supplier, found)
        self.assertIn(supplier, Partner.search(Partner._tag_domain('vendor', 'donor', any_of=True)))

    def test_bill_and_invoice_partner_tags(self):
        Move = self.env['account.move']
        vendor = self.env.ref('bn_profile_management.vendor_partner_category')
        donor = self.env.ref('bn_profile_management.donor_partner_category')
        self.assertEqual(Move.new({'move_type': 'in_invoice'}).partner_tag_ids._origin, vendor)
        self.assertEqual(Move.new({'move_type': 'out_invoice'}).partner_tag_ids._origin, donor)
        self.assertFalse(Move.new({'move_type': 'entry'}).partner_tag_ids)

    def test_default_partner_tags(self):
        Partner = self.env['res.partner'].with_context(default_partner_tags='donee,individual,medical')
        values = Partner.default_get(['category_id'])
        expected = {self.env.ref('bn_profile_management.%s_partner_category' % t).id for t in ('donee', 'individual', 'medical')}
        self.assertEqual(set(values['category_id'][0][2]), expected)
