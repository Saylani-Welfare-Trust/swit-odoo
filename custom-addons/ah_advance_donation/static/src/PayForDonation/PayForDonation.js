/** @odoo-module **/

import {useService} from "@web/core/utils/hooks";
import { useState } from "@odoo/owl";
import {ErrorPopup} from "@point_of_sale/app/errors/popups/error_popup";
import {AbstractAwaitablePopup} from "@point_of_sale/app/popup/abstract_awaitable_popup";
import {_t} from "@web/core/l10n/translation";



export class PayForDonation extends AbstractAwaitablePopup {
    static template = "ah_advance_donation.PayForDonationPopUp";

    setup() {
        const today = new Date();
        const formattedDate = today.toISOString().split('T')[0];

        this.popup = useService("popup");
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.title = "Advance Donation";
        this.bank_ids = this.props.bank_ids;
        this.state = useState({
            is_donation_id: true,
            donation_id: null,
            payment_type: 'cash',
            selected_bank_id: this.bank_ids[0].id,
            cheque_number: '',
            cheque_date: formattedDate,
            amount: '',
        });
    }
    onChangeIsDonationID(event) {
        this.state.is_donation_id = event.target.checked;
    }
    onChangeDonationID(event) {
        this.state.donation_id = event.target.value;
    }
    onPaymentMethodChange(event) {
        this.state.payment_type = event.target.value;
    }
    onBankChange(event) {
        this.state.selected_bank_id = event.target.value;
    }
    onChequeNumberChange(event) {
        this.state.cheque_number = event.target.value;
    }
    onChequeDateChange(event) {
        this.state.cheque_date = event.target.value;
    }
    onAmountChange(event) {
        this.state.amount = event.target.value;
    }

    async confirmPayment(){
        let data ={
            'is_donation_id': this.state.is_donation_id,
            'partner_id': 2,
            'donation_id': this.state.donation_id,
            'payment_type': this.state.payment_type,
            'amount': this.state.amount,
            'bank_id': this.state.selected_bank_id,
            'cheque_number': this.state.cheque_number,
            'cheque_date': this.state.cheque_date,
        }

        await this.orm.call('ah.advance.donation.receipt', "register_pos_payment", [data]).then((data) => {
            if (data.status === 'error') {
                this.popup.add(ErrorPopup, {
                    title: _t("Error"),
                    body: data.body,
                });
            }
            if (data.status === 'success') {
                this.notification.add(_t("Operation Successful"), {
                    type: "info",
                });
                this.cancel()
//                this.report.doAction("pos_microfinance_loan.report_mfd_installment_receipt", [
//                    data.report_id,
//                ]);
            }
        })
    }


}