/** @odoo-module **/

import {ProductScreen} from "@point_of_sale/app/screens/product_screen/product_screen";
import {useService} from "@web/core/utils/hooks";
import {Component} from "@odoo/owl";
import {usePos} from "@point_of_sale/app/store/pos_hook";
import { useState } from "@odoo/owl";


import {TextInputPopup} from "@point_of_sale/app/utils/input_popups/text_input_popup";
import {ErrorPopup} from "@point_of_sale/app/errors/popups/error_popup";

import {AbstractAwaitablePopup} from "@point_of_sale/app/popup/abstract_awaitable_popup";
import {_t} from "@web/core/l10n/translation";
import {sprintf} from "@web/core/utils/strings";

export class InputPopup extends AbstractAwaitablePopup{
      static template = "pos_microfinance_loan.InputPopup";

    setup() {
        const today = new Date();
        const formattedDate = today.toISOString().split('T')[0];
        console.log(formattedDate, 'formattedDate')

        this.report = useService("report");
        this.printer = useService("printer");
        this.pos = usePos();
        this.popup = useService("popup");
        this.orm = useService("orm");
        this.title = 'Create MFD Payment';
        this.loan_id = this.props.loan_id;
        this.bank_ids = this.props.bank_ids;
        this.amount = useState({ amount: '' });
        this.payment = useState({ payment_type: 'cash' });
        this.doc_type = useState({ doc_type: 'ins_dep' });
        this.selected_bank_id = useState({ bank_id: this.bank_ids.length > 0 ? this.bank_ids[0].id : '' });
        this.cheque_number = useState({ number: '' });
        this.cheque_date = useState({ date: formattedDate });
        this.notification = useService("notification");
    }

    onDocTypeChange(event) {
        this.doc_type.doc_type = event.target.value;
    }
    onPaymentMethodChange(event) {
        this.payment.payment_type = event.target.value;
    }
    onAmountChange(event) {
        this.amount.amount = event.target.value;
    }
    onBankChange(event) {
        this.selected_bank_id.bank_id = event.target.value;
    }
    onChequeNumberChange(event) {
        this.cheque_number.number = event.target.value;
    }
    onChequeDateChange(event) {
        this.cheque_date.date = event.target.value;
    }

    async confirmPayment(){
        let data ={
            'doc_type': this.doc_type.doc_type,
            'payment_type': this.payment.payment_type,
            'loan_id': this.loan_id.id,
            'currency_id': this.loan_id.currency_id,
            'amount': this.amount.amount,
            'bank_id': this.selected_bank_id.bank_id,
            'cheque_number': this.cheque_number.number,
            'cheque_date': this.cheque_date.date,
            'pos_session_id': this.pos.pos_session.id,
        }

        await this.orm.call('mfd.installment.receipt', "register_pos_mfd_payment", [data]).then((data) => {
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
                this.report.doAction("microfinance_loan.report_mfd_installment_receipt", [
                    data.report_id,
                ]);
            }
//            const reportId = data.report_id;
//            const reportTemplate = "pos_microfinance_loan.report_mfd_installment_receipt";

//            this.printer.print(reportTemplate, reportId, {
//                        template: reportTemplate, // Passing the report template
//                    });
            console.log("Printed data", data)
        })
    }
}

export class InstallmentPopup extends AbstractAwaitablePopup {
    static template = "pos_microfinance_loan.InstallmentPopup";

    setup() {
        this.pos = usePos();
        this.popup = useService("popup");
        this.orm = useService("orm");
        this.title = 'Loans';
        this.loan_ids = this.props.loan_ids;
        this.bank_ids = this.props.bank_ids;
        this.notification = useService("notification");
    }

    async onClick(loan_id) {
        this.popup.add(InputPopup, {
            loan_id: loan_id,
            bank_ids: this.bank_ids
        });
        this.cancel()
    }
}

export class MicrofinanceButton extends Component {
    static template = "pos_microfinance_loan.MicrofinanceButton";

    setup() {
        this.pos = usePos();
        this.popup = useService("popup");
        this.orm = useService("orm");
    }

    async onClick() {
        const {confirmed, payload: newName} = await this.popup.add(TextInputPopup, {
            title: _t("Enter CNIC number"),
            placeholder: _t("xxxxx-xxxxxxx-x"),
        });
        if (!confirmed) {
            return;
        }
        await this.orm.call('mfd.loan.request', "check_loan_ids", [newName])
            .then((data) => {
                if (data.status === 'error') {
                    this.popup.add(ErrorPopup, {
                        title: _t("Error"),
                        body: data.body,
                    });
                }
                if (data.status === 'success') {
                    this.popup.add(InstallmentPopup, {
                        loan_ids : data.loan_ids,
                        bank_ids: data.bank_ids
                    });
                }
            });
    }
}


ProductScreen.addControlButton({
    component: MicrofinanceButton,
});
