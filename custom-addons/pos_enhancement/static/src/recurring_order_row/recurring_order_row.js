/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
// import { deserializeDateTime } from "@web/core/l10n/dates";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { PaymentPopup } from "../PaymentPopup/paymentpopup";
import { Payment } from "@point_of_sale/app/store/models";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import {serializeDateTime, deserializeDateTime} from "@web/core/l10n/dates";
const { DateTime } = luxon;

/**
 * @props {models.Order} order
 * @props columns
 * @emits click-order
 */
export class RecurringOrderRow extends Component {
    static template = "pos_enhancement.RecurringOrderRow";

    setup() {
        this.ui = useState(useService("ui"));
        this.printer=useService("printer");
        this.popup = useService("popup");
        this.pos=usePos()
    }
    capitalizeFirstLetter(str) {
        let capitalizedWords=[];
        if (str){
            let words = str.split('_');
            capitalizedWords = words.map(word => {
                return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
            });

        }
    
        return capitalizedWords.join(' ');
    }
    get order() {
        return this.props.order;
    }

    get highlighted() {
        const highlightedOrder = this.props.highlightedOrder;
        return !highlightedOrder
            ? false
            : highlightedOrder.backendId === this.props.order.backendId;
    }

    get name() {
        return this.order.name;
    }

    get date() {
        return deserializeDateTime(this.order.create_date).toFormat("yyyy-MM-dd HH:mm a");
    }

    get partner() {
        const partner = this.order.partner_id;
        return partner ? partner[1] : null;
    }

    get registrar() {
        const registrar = this.order.registrar;
        return registrar ? registrar[1] : null;
    }
    get disbursment_type(){
        const disbursment_type = this.order.disbursement_type;
        return this.capitalizeFirstLetter(disbursment_type);
    }
    get transaction_type(){
        const transaction_type = this.order.transaction_type;
        return this.capitalizeFirstLetter(transaction_type);
    }
    async print() {   
        // const order=this.pos.get_order()
        console.log(this.order)
        if (this.order.amount_total && !this.order.is_payment_validated) {
            const { confirmed, payload } = await this.popup.add(PaymentPopup, {
                title: "payment" ,
                startingValue: this.order.amount_total,
                isInputSelected: true,
                nbrDecimal: this.pos.currency.decimal_places,
                inputSuffix: this.pos.currency.symbol,
            });
            if (confirmed) {
                if (payload[0] != this.order.amount_total) {
                    this.popup.add(ErrorPopup, {
                        title: _t("Error"),
                        body: "Please Enter Correct amount",
                    });
                }
                else{
                    // const payment = new Payment(payload[1])
                    const payment=[[0, 0, {'name': serializeDateTime(DateTime.local()), 'payment_method_id': payload[1].id, 'amount': payload[0], 'payment_status': '', 'ticket': '', 'card_type': '', 'cardholder_name': '', 'transaction_id': ''}]]
                    // console.log("payload",payment)
                    this.pos.showScreen("PrintRegisterOrderScreen", { order: this.order, payment:payment });

                }
            }

        }
        else{
            this.pos.showScreen("PrintRegisterOrderScreen", { order: this.order });
        }
    }
}
