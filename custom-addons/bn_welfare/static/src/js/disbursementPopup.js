/** @odoo-module **/

import {useService} from "@web/core/utils/hooks";
import {usePos} from "@point_of_sale/app/store/pos_hook";
import { useState } from "@odoo/owl";

import {ErrorPopup} from "@point_of_sale/app/errors/popups/error_popup";

import {AbstractAwaitablePopup} from "@point_of_sale/app/popup/abstract_awaitable_popup";
import {_t} from "@web/core/l10n/translation";


export class DisbursementListPopup extends AbstractAwaitablePopup{
    static template = "bn_welfare.DisbursementListPopup";

  setup() {
      const today = new Date();
      const formattedDate = today.toISOString().split('T')[0];
      console.log(formattedDate, 'formattedDate')
      
      const flattenedCollectionIds = this.collection_ids.flat();
      console.log(flattenedCollectionIds, 'Flat Collection IDs')

      this.report = useService("report");
      this.printer = useService("printer");
      this.pos = usePos();
      this.popup = useService("popup");
      this.orm = useService("orm");
      this.title = 'Create Disbursement Payment';
      this.disbursement_id = this.props.disbursement_id;
      this.collection_ids = this.props.collection_ids;
      this.amount = useState({ amount: '' });
      this.payment = useState({ payment_type: 'cash' });
      this.selected_collection_id = useState({ collection_id: flattenedCollectionIds.length > 0 ? flattenedCollectionIds[0].id : '' });
      this.cheque_number = useState({ number: '' });
      this.cheque_date = useState({ date: formattedDate });
      this.notification = useService("notification");
  }

  onPaymentMethodChange(event) {
      this.payment.payment_type = event.target.value;
  }
  onAmountChange(event) {
      this.amount.amount = event.target.value;
  }
  onCollectionChange(event) {
      this.selected_collection_id.collection_id = event.target.value;
  }
  onChequeNumberChange(event) {
      this.cheque_number.number = event.target.value;
  }
  onChequeDateChange(event) {
      this.cheque_date.date = event.target.value;
  }

  async confirmDisbursement(){
      let data ={
          'payment_type': this.payment.payment_type,
          'disbursement_id': this.disbursement_id.id,
          'disbursement_number': disbursement_id.name,
          'currency_id': this.disbursement_id.currency_id,
          'amount': this.amount.amount,
          'collection_id': this.selected_collection_id.collection_id,
          'cheque_number': this.cheque_number.number,
          'cheque_date': this.cheque_date.date,
          'pos_session_id': this.pos.pos_session.id,
          'res_model': this.disbursement_id.res_model,
      }

      await this.orm.call('disbursement.request', "mark_as_disbursed", [data]).then((data) => {
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
            
            }
            
            this.report.doAction("bn_welfare.disbursement_slip_report_action", [
                data.report_id,
            ]);

            console.log("Printed Disbursement Data", data)
      })
  }
}

export class DisbursementPopup extends AbstractAwaitablePopup {
    static template = "bn_welfare.DisbursementPopup";

    setup() {
        this.pos = usePos();
        this.report = useService("report");
        this.popup = useService("popup");
        this.orm = useService("orm");
        this.title = 'Disbursement';
        this.disbursement_ids = this.props.disbursement_ids;
        this.collection_ids = this.props.collection_ids;
        this.notification = useService("notification");
    }

    async onClick(disbursement_id) {
        let data ={
            'disbursement_id': disbursement_id.id,
            'disbursement_number': disbursement_id.name,
            'res_model': disbursement_id.res_model,
        }

        await this.orm.call('disbursement.request', "mark_as_disbursed", [data]).then((data) => {
            if (data.status === 'error') {
                this.popup.add(ErrorPopup, {
                    title: _t("Error"),
                    body: data.body,
                });
            }
            if (data.status === 'success') {
                this.notification.add(_t("Record has been Disbursed Successful"), {
                    type: "info",
                });
                this.cancel()
            }
  
            this.report.doAction("bn_welfare.disbursement_slip_report_action", [
                data.report_id,
            ]);

            console.log("Printed Disbursement Data", data)
        })
    }
}