/** @odoo-module */

import { PartnerDetailsEdit } from "@point_of_sale/app/screens/partner_list/partner_editor/partner_editor";
import { patch } from "@web/core/utils/patch";

patch(PartnerDetailsEdit.prototype, {
    setup(){
        super.setup(...arguments);
        console.log("user ",this.pos.env.services.user)
        delete this.changes.state_id;
        delete this.changes.country_id;
        delete this.changes.property_product_pricelist;

        this.changes.company_type= this.props.partner.company_type || "person"
        this.changes.bank_name= this.props.partner.bank_name || ""
        // this.changes.bank_account_no= this.props.partner.bank_account_no || ""
        this.changes.disbursement_type= this.props.partner.disbursement_type || ""
        this.changes.transaction_type= this.props.partner.transaction_type || ""
        this.changes.cash_transaction_type= this.props.partner.cash_transaction_type || ""
        this.changes.in_kind_transaction_type= this.props.partner.in_kind_transaction_type || ""

        // for individual
        this.changes.gender= this.props.partner.gender || ""
        this.changes.cnic_no= this.props.partner.cnic_no || ""
        this.changes.date_of_birth= this.props.partner.date_of_birth || false
        // this.changes.reference_person_cnic= this.props.partner.reference_person_cnic || false
        this.changes.age= this.props.partner.age || ""

        // for institution
        this.changes.reg_no= this.props.partner.reg_no || ""
        this.changes.date_of_incorporation= this.props.partner.date_of_incorporation || false
        this.changes.institution_referred_by= this.props.partner.institution_referred_by || ""
        this.changes.authorized_person_name= this.props.partner.authorized_person_name || ""
        this.changes.authorized_person_cell= this.props.partner.authorized_person_cell || ""
        this.changes.authorized_person_cnic= this.props.partner.authorized_person_cnic || ""
        },
    formatItem(item) {
        return item.toLowerCase().replace(/\s+/g, '_')
    },

});

