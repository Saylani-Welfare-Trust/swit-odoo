/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { TextInputPopup } from "@point_of_sale/app/utils/input_popups/text_input_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { CustomButtonPopup } from "@sm_point_of_sale_apps/js/CustomButtonPopup/CustomButtonPopup";
import { InstallmentPopup } from "@pos_microfinance_loan/js/button";
import { DisbursementPopup } from "@bn_welfare/js/disbursementPopup";
import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";

export class CustomScanCard extends Component {
    static template = "sm_point_of_sale_apps.CustomScanCard";

    setup() {
        this.pos = usePos();
        this.popup = useService("popup");
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.report = useService("report");
    }

    async onClick() {
        const { confirmed, payload: data } = await this.popup.add(CustomButtonPopup, {
            title: _t("Scan Card"),
        });

        console.log(`Hit Disbursement ${JSON.stringify(data)}`);

        


        if (confirmed) {
            if (data.type_value=="med_eq") {
                this.report.doAction("sm_point_of_sale_apps.medical_equipment_report_action", [
                            data.DonationBox_id,
                        ]);
            }
            if (data.type_value=="dhs") {
                this.report.doAction("sm_point_of_sale_apps.donation_home_service_report_action", [
                            data.DonationBox_id,
                        ]);
            }
            if(data.scan_card_value) {
                let partner=this.pos.db.get_partner_by_barcode(data.scan_card_value);
                let order=this.pos.get_order()
                order.set_partner(partner)
            }
            if(data.cnic_number_value) {
                let partner=this.pos.db.get_partner_by_barcode(data.scan_card_value);
                let order=this.pos.get_order()
                order.set_partner(partner)
                await this.orm.call('mfd.loan.request', "check_loan_ids", [data.cnic_number_value]).then((data) => {
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
            if(data.disbursement_value) {
                let partner=this.pos.db.get_partner_by_barcode(data.scan_card_value);
                let order=this.pos.get_order()
                order.set_partner(partner)
                
                if (data.order_type_value == 'one_time') {
                    await this.orm.call('disbursement.request', "check_disbursement_ids", [data.disbursement_value]).then((data) => {
                        if (data.status === 'error') {
                            this.popup.add(ErrorPopup, {
                                title: _t("Error"),
                                body: data.body,
                            });
                        }
                        if (data.status === 'success') {
                            this.popup.add(DisbursementPopup, {
                                disbursement_ids : data.disbursement_ids,
                                collection_ids: data.collection_ids
                            });
                        }
                    });
                }
                else {
                    await this.orm.call('disbursement.request', "check_recurring_disbursement_ids", [data.disbursement_value]).then((data) => {
                        if (data.status === 'error') {
                            this.popup.add(ErrorPopup, {
                                title: _t("Error"),
                                body: data.body,
                            });
                        }
                        if (data.status === 'success') {
                            this.popup.add(DisbursementPopup, {
                                disbursement_ids : data.disbursement_ids,
                                collection_ids: data.collection_ids
                            });
                        }
                    });
                }
            }
            if(data.key_value) {
                let partner=this.pos.db.get_partner_by_barcode(data.scan_card_value);
                let order=this.pos.get_order()
                order.set_partner(partner)
                
                const payroll = {
                    'key': data.key_value,
                    'amount': data.collection_amount_value
                } 
                
                await this.orm.call('key.issuance', "set_donation_amount", [payroll]).then((data) => {
                    if (data.status === 'error') {
                        this.popup.add(ErrorPopup, {
                            title: _t("Error"),
                            body: data.body,
                        });
                    }
                    if (data.status === 'success') {
                        this.notification.add(_t("Amount Recorded Successful"), {
                            type: "info",
                        });
                        this.report.doAction("sm_point_of_sale_apps.donationbox_slip_report_action", [
                            data.DonationBox_id,
                        ]);
                    }

                });
            }
        }
    }
}

ProductScreen.addControlButton({
    component: CustomScanCard,
});
