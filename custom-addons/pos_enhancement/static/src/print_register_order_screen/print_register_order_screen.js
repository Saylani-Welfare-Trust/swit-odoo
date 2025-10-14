/** @odoo-module */

import { usePos } from "@point_of_sale/app/store/pos_hook";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { onWillStart } from "@odoo/owl";
import { Component, useState} from "@odoo/owl";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";
import { Numpad } from "@point_of_sale/app/generic_components/numpad/numpad";
import { _t } from "@web/core/l10n/translation";

export class PrintRegisterOrderScreen extends Component {
    static template = "pos_enhancement.PrintRegisterOrderScreen";
    static components = { OrderReceipt,Numpad };
    static storeOnOrder = false;
    // static props = ["order"];

    setup() {
        super.setup();
        this.pos = usePos();
        this.printer = useService("printer");
        this.popup=useService("popup");
        this.orm=useService("orm");

        this.state=useState({
            order:null
        })
        onWillStart(async () => {
            console.log("this.props.order", this.props)

            // const { confirmed, payload } = await this.popup.add(NumberPopup, {
            //     title: "payment" ,
            //     startingValue: 899,
            //     isInputSelected: true,
            //     nbrDecimal: this.pos.currency.decimal_places,
            //     inputSuffix: this.pos.currency.symbol,
            // });
            // if (confirmed) {

                const res= await this.orm.call('pos.registered.order','export_for_printing',[[this.props.order.id],this.props.payment])
                // console.log(res)
                if (res.error){
                    // this.pos.showScreen("RecurringOrderScreen");
                    console.log(res.error)
                    this.popup.add(ErrorPopup, {
                        title: _t("Error"),
                        body: res.error,
                    });

                }
                else{
                    res['headerData'] = {...this.pos.getReceiptHeaderData(this)}
                    res['footer']=this.pos.config.receipt_footer,
                    // console.log(res)
                    this.state.order = res

                }
            // }
        })
    }

    confirm() {
        this.pos.showScreen("RecurringOrderScreen");
    }

    tryReprint() {


        this.printer.print(
            OrderReceipt,
            {
                data: this.state.order,
                formatCurrency: this.env.utils.formatCurrency,
            },
            { webPrintFallback: true }
        );
    }


}

registry.category("pos_screens").add("PrintRegisterOrderScreen", PrintRegisterOrderScreen);
