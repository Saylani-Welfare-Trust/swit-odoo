/** @odoo-module */
import { useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import {CustomButtonPopup} from "@sm_point_of_sale_apps/js/CustomButtonPopup/CustomButtonPopup";

patch(CustomButtonPopup.prototype, {
    setup() {
        super.setup();
        this.dhs = useState({ dhs_value: '' });
        this.med_eq = useState({ med_eq_value: '' });
        this.ration_bag = useState({ ration_bag_value: '' });
        this.medicine = useState({ medicine_value: '' });
        this.disbursement = useState({ disbursement_value: '' });
        this.order_type = useState({ order_type_value: '' });
        this.key = useState({ key_value: '' });
        this.collection_amount = useState({ collection_amount: '' });
    },

    onTypeChange(event) {
    this.type.type_value = event.target.value;
    if(event.target.value == 'scan_card') {
        $('.scan_card').css('display', 'block');
        $('.cnic_number').css('display', 'none');
        $('.dhs').css('display', 'none');
        $('.med_eq').css('display', 'none');
        $('.ration_bag').css('display', 'none');
        $('.medicine').css('display', 'none');
        $('.disbursement').css('display', 'none');
        $('.donation_box').css('display', 'none');
        this.cnic_number.cnic_number_value = '';
    }
    else if(event.target.value == 'microfinance_installment'){
        $('.cnic_number').css('display', 'block');
        $('.dhs').css('display', 'none');
        $('.scan_card').css('display', 'none');
        $('.med_eq').css('display', 'none');
        $('.ration_bag').css('display', 'none');
        $('.medicine').css('display', 'none');
        $('.disbursement').css('display', 'none');
        $('.donation_box').css('display', 'none');
        this.scan_card.scan_card_value = '';
    }
    else if(event.target.value == 'dhs'){
        $('.dhs').css('display', 'block');
        $('.cnic_number').css('display', 'none');
        $('.scan_card').css('display', 'none');
        $('.med_eq').css('display', 'none');
        $('.ration_bag').css('display', 'none');
        $('.medicine').css('display', 'none');
        $('.disbursement').css('display', 'none');
        $('.donation_box').css('display', 'none');
        this.dhs.dhs_value = '';
    }
    else if(event.target.value == 'med_eq'){
        $('.med_eq').css('display', 'block');
        $('.scan_card').css('display', 'none');
        $('.cnic_number').css('display', 'none');
        $('.dhs').css('display', 'none');
        $('.ration_bag').css('display', 'none');
        $('.medicine').css('display', 'none');
        $('.disbursement').css('display', 'none');
        $('.donation_box').css('display', 'none');
        this.med_eq.med_eq_value = '';
    }
    else if(event.target.value == 'ration_bag'){
        $('.ration_bag').css('display', 'block');
        $('.scan_card').css('display', 'none');
        $('.cnic_number').css('display', 'none');
        $('.dhs').css('display', 'none');
        $('.med_eq').css('display', 'none');
        $('.medicine').css('display', 'none');
        $('.disbursement').css('display', 'none');
        $('.donation_box').css('display', 'none');
        this.ration_bag.ration_bag_value = '';
    }
    else if(event.target.value == 'disbursement'){
        $('.disbursement').css('display', 'block');
        $('.medicine').css('display', 'none');
        $('.scan_card').css('display', 'none');
        $('.cnic_number').css('display', 'none');
        $('.dhs').css('display', 'none');
        $('.med_eq').css('display', 'none');
        $('.ration_bag').css('display', 'none');
        $('.donation_box').css('display', 'none');
        this.disbursement.disbursement_value = '';
        this.order_type.order_type_value = '';
    }
    else if(event.target.value == 'donation_box'){
        $('.donation_box').css('display', 'block');
        $('.disbursement').css('display', 'none');
        $('.medicine').css('display', 'none');
        $('.scan_card').css('display', 'none');
        $('.cnic_number').css('display', 'none');
        $('.dhs').css('display', 'none');
        $('.med_eq').css('display', 'none');
        $('.ration_bag').css('display', 'none');
        this.key.key_value = '';
        this.collection_amount.collection_amount_value = '';
    }
    else {
        $('.medicine').css('display', 'block');
        $('.scan_card').css('display', 'none');
        $('.cnic_number').css('display', 'none');
        $('.dhs').css('display', 'none');
        $('.med_eq').css('display', 'none');
        $('.ration_bag').css('display', 'none');
        $('.disbursement').css('display', 'none');
        $('.donation_box').css('display', 'none');
        this.medicine.medicine_value = '';
    }
    },

    onDhsChange(event){
    this.dhs.dhs_value = event.target.value;
    },
    onMedEqChange(event) {
    this.med_eq.med_eq_value = event.target.value;
    },
    onRationBagChange(event) {
    this.ration_bag.ration_bag_value = event.target.value;
    },
    onMedicineChange(event) {
    this.medicine.medicine_valuei = event.target.value;
    },
    onDisbursementChange(event) {
    this.disbursement.disbursement_value = event.target.value;
    },
    onOrderTypeChange(event) {
    this.order_type.order_type_value = event.target.value;
    },
    onKeyChange(event) {
    this.key.key_value = event.target.value;
    },
    onCollectionAmountChange(event) {
    this.collection_amount.collection_amount_value = event.target.value;
    },

    getPayload() {
        return {
            type_value: this.type.type_value,
            scan_card_value: this.scan_card.scan_card_value,
            cnic_number_value: this.cnic_number.cnic_number_value,
            dhs_value: this.dhs.dhs_value,
            disbursement_value: this.disbursement.disbursement_value,
            order_type_value: this.order_type.order_type_value,
            key_value: this.key.key_value,
            collection_amount_value: this.collection_amount.collection_amount_value,
        };
   }

});