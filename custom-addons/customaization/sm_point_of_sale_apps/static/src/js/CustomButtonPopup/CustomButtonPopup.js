/** @odoo-module */
import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { _t } from "@web/core/l10n/translation";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useRef, onMounted, useState } from "@odoo/owl";

export class CustomButtonPopup extends AbstractAwaitablePopup {
   static template = "custom_popup.CustomButtonPopup";
   static defaultProps = {
       closePopup: _t("Cancel"),
       confirmText: _t("Confirm"),
       title: _t("Scan Card"),
   };

   setup() {
        super.setup();
        this.type = useState({ type_value: 'scan_card' });
        this.scan_card = useState({ scan_card_value: '' });
        this.cnic_number = useState({ cnic_number_value: '' });
   }

   onTypeChange(event) {
        this.type.type_value = event.target.value;
        if(event.target.value == 'scan_card') {
            $('.scan_card').css('display', 'block');
            $('.cnic_number').css('display', 'none');
            this.cnic_number.cnic_number_value = '';
        }
        else {
            $('.scan_card').css('display', 'none');
            $('.cnic_number').css('display', 'block');
            this.scan_card.scan_card_value = '';
        }
   }

   onScanCardChange(event) {
        this.scan_card.scan_card_value = event.target.value;
   }
   
   onCnicNumberChange(event) {
        this.cnic_number.cnic_number_value = event.target.value;
   }
   _onWindowKeyup(event) {
        if (event.key === this.props.confirmKey) {
            this.confirm();
        } else {
            super._onWindowKeyup(...arguments);
        }
   }
   getPayload() {
        return {
            type_value: this.type.type_value,
            scan_card_value: this.scan_card.scan_card_value,
            cnic_number_value: this.cnic_number.cnic_number_value,
        };
   }
}