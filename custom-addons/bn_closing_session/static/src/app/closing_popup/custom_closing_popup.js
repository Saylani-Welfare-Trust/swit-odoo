/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { SaleDetailsButton } from "@point_of_sale/app/navbar/sale_details_button/sale_details_button";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";
import { MoneyDetailsPopup } from "@point_of_sale/app/utils/money_details_popup/money_details_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

import { useService } from "@web/core/utils/hooks";
import { useState, onMounted } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useAsyncLockedMethod } from "@point_of_sale/app/utils/hooks";

import { ConnectionLostError } from "@web/core/network/rpc_service";
import { _t } from "@web/core/l10n/translation";

export class CustomClosingPopup extends AbstractAwaitablePopup {
    static template = "CustomClosingPopup";
    static components = { SaleDetailsButton };

    setup() {
        super.setup();

        this.pos = usePos();
        this.popup = useService("popup");
        this.orm = useService("orm");
        this.report = useService("report");
        this.hardwareProxy = useService("hardware_proxy");

        this.state = useState({
            notes: "",
            payments: {},
            lines: {},
            newLines: {},
        });

        this._init();

        this.handleAddLine = this.handleAddLine.bind(this);
        this.handleRemoveLine = this.handleRemoveLine.bind(this);
        this.confirm = useAsyncLockedMethod(this.confirm);
    }

    _init() {
        const all = [this.props.default_cash_details, ...(this.props.other_payment_methods || [])];

        all.forEach(pm => {
            if (!pm) return;

            this.state.payments[pm.id] = { counted: "0" };

            this.state.lines[pm.id] = {
                restricted: [],
                unrestricted: [],
                neutral: []
            };

            this.state.newLines[pm.id] = {
                restricted: { bank: "", amount: 0, ref: "" },
                unrestricted: { bank: "", amount: 0, ref: "" },
                neutral: { bank: "", amount: 0, ref: "" }
            };
        });
    }

    _getPayment(id) {
        if (id === this.props.default_cash_details?.id) return this.props.default_cash_details;
        return (this.props.other_payment_methods || []).find(p => p.id === id);
    }

    getLinesTotal(id) {
        const l = this.state.lines[id];
        return ["restricted","unrestricted","neutral"]
            .flatMap(t => l[t])
            .reduce((s,x)=>s+(x.amount||0),0);
    }

    getDifference(id) {
        const pm = this._getPayment(id);
        const counted = parseFloat(this.state.payments[id]?.counted || 0);
        return counted + this.getLinesTotal(id) - (pm.amount || 0);
    }

    getRestrictedDifference(id){
        const pm=this._getPayment(id);
        return (this.state.lines[id].restricted.reduce((s,l)=>s+l.amount,0))
            - (pm.breakdown.restricted||0);
    }

    getUnrestrictedDifference(id){
        const pm=this._getPayment(id);
        return (this.state.lines[id].unrestricted.reduce((s,l)=>s+l.amount,0))
            - (pm.breakdown.unrestricted||0);
    }

    getNeutralDifference(id){
        const pm=this._getPayment(id);
        return (this.state.lines[id].neutral.reduce((s,l)=>s+l.amount,0))
            - (pm.breakdown.neutral||0);
    }

    formatCurrencyNeutral(v){
        return this.env.utils.formatCurrency(Number(v)||0);
    }

    shouldShowSlipInput(pm){
        return !(pm.skip_amount_input);
    }

    shouldShowSlipHeaders(){
        return true;
    }

    canConfirm(){
        return true;
    }

    async handleAddLine(paymentId, type){
        const d=this.state.newLines[paymentId][type];
        if(!d.ref || !d.amount) return;

        this.state.lines[paymentId][type].push({
            id:Date.now(),
            bank:d.bank,
            amount:Number(d.amount),
            ref:d.ref
        });

        this.state.newLines[paymentId][type]={bank:"",amount:0,ref:""};
    }

    async handleRemoveLine(paymentId,lineId,record_id,type){
        this.state.lines[paymentId][type]=
            this.state.lines[paymentId][type].filter(l=>l.id!==lineId);
    }

    async confirm(){
        return this.closeSession();
    }

    async closeSession(){
        try{
            await this.orm.call("pos.session","close_session_from_ui",[
                this.pos.pos_session.id,
                [],
                this.state.lines
            ]);
            this.pos.redirectToBackend();
        }catch(e){
            await this.popup.add(ErrorPopup,{title:"Error",body:"Closing failed"});
        }
    }

    async downloadSalesReport(){
        return this.report.doAction("point_of_sale.sale_details_report",[this.pos.pos_session.id]);
    }

    async cancel(){
        super.cancel();
    }
}