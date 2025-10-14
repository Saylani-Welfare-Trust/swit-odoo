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


export class DonationHomeServiceButton extends Component{
    static template = "ah_donation_home_service.DonationHomeServiceButton";

    setup() {
        this.pos = usePos();
        this.popup = useService("popup");
        this.orm = useService("orm");
        this.notification = useService("notification");
    }

    async NewDonationOrder() {
        const selectedOrder = this.pos.get_order();
        const pos_total = 0

        if (selectedOrder) {
            const pos_total = selectedOrder.get_total_with_tax();
            const orderLines = selectedOrder.get_orderlines()

            console.log(orderLines, 'orderLines')

            if (orderLines.length == 0) {
                this.popup.add(ErrorPopup, {
                    title: _t("Error"),
                    body: "Please select product",
                });
                return;
            }

            const customer_id = selectedOrder.partner ? selectedOrder.partner.id : null;

            if (!customer_id) {
                this.popup.add(ErrorPopup, {
                    title: _t("Error"),
                    body: "Please select Customer",
                });
                return;
            }

            const customer_name = selectedOrder.partner.name;
            const customer_address = selectedOrder.partner.street;

            this.orm.call('dhs.product.conf', "get_dhs_products").then((data) => {
                const invalidOrderLine = orderLines.find(line => !data.includes(line.product.id));
                console.log(invalidOrderLine, 'invalidOrderLine')
                if (invalidOrderLine) {
                    this.popup.add(ErrorPopup, {
                        title: _t("Error"),
                        body: "This product is not allowed for Donation Home Service",
                    });
                    return;
                }
                this.popup.add(NewDonationOrderPoPup, {
                    pos_total: pos_total,
                    customer_id: customer_id,
                    customer_name: customer_name,
                    customer_address: customer_address,
                    orderLines: orderLines
                });
            });

        }
    }
}


export class SelectionPopUp extends AbstractAwaitablePopup {
    static template = "ah_donation_home_service.OperationSelection";

    setup() {
        this.pos = usePos();
        this.popup = useService("popup");
        this.orm = useService("orm");
        this.notification = useService("notification");
    }

    async NewDonationOrder() {
        const selectedOrder = this.pos.get_order();
        const pos_total = 0

        if (selectedOrder) {
            const pos_total = selectedOrder.get_total_with_tax();
            const orderLines = selectedOrder.get_orderlines()


            if (orderLines.length == 0) {
                this.popup.add(ErrorPopup, {
                    title: _t("Error"),
                    body: "Please select product",
                });
                this.cancel();
                return;
            }

            const customer_id = selectedOrder.partner ? selectedOrder.partner.id : null;

            if (!customer_id) {
                this.popup.add(ErrorPopup, {
                    title: _t("Error"),
                    body: "Please select Customer",
                });
                this.cancel();
                return;
            }

            const customer_name = selectedOrder.partner.name;
            const customer_address = selectedOrder.partner.street;

            this.popup.add(NewDonationOrderPoPup, {
                pos_total: pos_total,
                customer_id: customer_id,
                customer_name: customer_name,
                customer_address: customer_address,
                orderLines: orderLines
            });
            this.cancel();
        }
    }

    async PayForDonation(){
        let is_cancel = false;
        const {confirmed, payload: newName} = await this.popup.add(TextInputPopup, {
            title: _t("Enter Donation ID"),
            placeholder: _t("DHS/xxxx"),
        });
        if (!confirmed) {
            return;
        }
        const selectedOrder = this.pos.get_order();
        await this.orm.call('donation.home.service', "check_donation_id", [newName, false])
            .then((data) => {
                if (data.status === 'error') {
                    this.popup.add(ErrorPopup, {
                        title: _t("Error"),
                        body: data.body,
                    });
                }
                if (data.status === 'success') {
                    this.popup.add(PayForDonationPopUp, {
                        donation_id: data.donation_id,
                        donation_name: data.donation_name,
                        donation_amount: data.donation_amount,
                        payment_type: data.payment_type
                    });
                    this.cancel();
                }
                this.pos.removeOrder(selectedOrder);
                this.pos.add_new_order();
                this.pos.resetProductScreenSearch();
        });
    }

    async CancelDonation(){
        let is_cancel = true;
        const {confirmed, payload: newName} = await this.popup.add(TextInputPopup, {
            title: _t("Enter Donation ID"),
            placeholder: _t("DHS/xxxx"),
        });
        if (!confirmed) {
            return;
        }
        const selectedOrder = this.pos.get_order();
        await this.orm.call('donation.home.service', "check_donation_id", [newName, is_cancel])
            .then((data) => {
                if (data.status === 'error') {
                    this.popup.add(ErrorPopup, {
                        title: _t("Error"),
                        body: data.body,
                    });
                }
                if (data.status === 'success') {
                    this.notification.add(_t(data.body), {
                        type: "info",
                    });
                    this.cancel();
                }
                this.pos.removeOrder(selectedOrder);
                this.pos.add_new_order();
                this.pos.resetProductScreenSearch();
         });
    }
}


export class NewDonationOrderPoPup extends AbstractAwaitablePopup {
    static template = "ah_donation_home_service.NewDonationOrderPoPup";

    setup() {
        this.report = useService("report");
        this.notification = useService("notification");
        this.pos = usePos();
        this.popup = useService("popup");
        this.orm = useService("orm");
        this.title = "New Donation Order";
        this.customer_id = this.props.customer_id;
        this.customer_name = this.props.customer_name;
        this.customer_address = this.props.customer_address;
        this.orderLines = this.props.orderLines
        this.state = useState({
            payment_type: 'cash',
            subtotal: parseFloat(this.props.pos_total),
            delivery_charges: 0,
            total: parseFloat(this.props.pos_total)
        });
    }

    onPaymentTypeChange(event) {
        this.state.payment_type = event.target.value;
    }
    onDeliveryChargesChange(event) {
        const deliveryCharges = parseFloat(event.target.value)
        this.state.delivery_charges = deliveryCharges;
        this.state.total = this.state.subtotal + this.state.delivery_charges
    }

    prepareOrderLines(orderLines) {
        return orderLines.map(line => (
                {
                    product_id: line.product.id,
                    quantity: line.quantity,
                }
            )
        );
    }

    async confirmDonation(){
        let data ={
            'partner_id': this.customer_id,
            'payment_type': this.state.payment_type,
            'order_lines': this.prepareOrderLines(this.orderLines),
            'delivery_charges': this.state.delivery_charges,
        }

        const selectedOrder = this.pos.get_order();

        await this.orm.call('donation.home.service', "register_pos_donation", [data]).then((data) => {
            if (data.status === 'success') {
                this.notification.add(_t("Operation Successful"), {
                    type: "info",
                });
//                this.pos.removeOrder(this.currentOrder);
                this.cancel()
                this.report.doAction("ah_donation_home_service.report_donation_home_service", [
                    data.donation_id,
                 ]);
            }
            this.pos.removeOrder(selectedOrder);
            this.pos.add_new_order();
            this.pos.resetProductScreenSearch();
////            const reportId = data.report_id;
////            const reportTemplate = "microfinance_loan.report_mfd_installment_receipt";
//            this.report.doAction("microfinance_loan.report_mfd_installment_receipt", [
//                    data.report_id,
//            ]);
////            this.printer.print(reportTemplate, reportId, {
////                        template: reportTemplate, // Passing the report template
////                    });
//            console.log("Printed data", data)
          })
     }
}


export class PayForDonationPopUp extends AbstractAwaitablePopup {
    static template = "ah_donation_home_service.PayForDonationPopUp";

    setup() {
        const today = new Date();
        const formattedDate = today.toISOString().split('T')[0];

        this.report = useService("report");
        this.notification = useService("notification");
        this.pos = usePos();
        this.popup = useService("popup");
        this.orm = useService("orm");
        this.title = "Pay for Donation";
        this.donation_id = this.props.donation_id;
        this.donation_name = this.props.donation_name;
        this.total_amount = parseFloat(this.props.donation_amount);
        this.state = useState({
            payment_type: this.props.payment_type,
            bank_name: '',
            cheque_number: '0',
            cheque_date: formattedDate
        });
    }

    onPaymentTypeChange(event) {
        this.state.payment_type = event.target.value;
    }
    onBankChange(event) {
        this.state.bank_name = event.target.value;
    }
    onChequeNumberChange(event) {
        this.state.cheque_number = event.target.value;
    }
    onChequeDateChange(event) {
        this.state.cheque_date = event.target.value;
    }

    async confirmPayment(){
        let data ={
            'donation_id': this.donation_id,
            'payment_type': this.state.payment_type,
            'bank_name': this.state.bank_name,
            'cheque_number': this.state.cheque_number,
            'cheque_date': this.state.cheque_date
        }

        await this.orm.call('donation.home.service', "confirm_pos_payment", [data]).then((data) => {
            if (data.status === 'error') {
                this.popup.add(ErrorPopup, {
                    title: _t("Error"),
                    body: data.body,
                });
                return;
            }
            if (data.status === 'success') {
                this.notification.add(_t("Operation Successful"), {
                    type: "info",
                });
                this.cancel();
                this.report.doAction("ah_donation_home_service.report_donation_home_service", [data.donation_id]);
            }
        })
     }
}



ProductScreen.addControlButton({
    component: DonationHomeServiceButton,
});
