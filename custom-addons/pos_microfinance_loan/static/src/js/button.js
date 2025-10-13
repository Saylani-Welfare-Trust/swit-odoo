



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
        console.log(formattedDate, 'formattedDate');

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

        console.log('Loan object:', this.loan_id);
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

    async confirmPayment() {
        let data = {
            'doc_type': this.doc_type.doc_type,
            'payment_type': this.payment.payment_type,
            'loan_id': this.loan_id.id,
            'currency_id': this.loan_id.currency_id,
            'amount': this.amount.amount,
            'bank_id': this.selected_bank_id.bank_id,
            'cheque_number': this.cheque_number.number,
            'cheque_date': this.cheque_date.date,
            'pos_session_id': this.pos.pos_session.id,
            'partner_id': this.loan_id.customer_name, 
           
            
        };
         console.log('Data to be sent:',  this.loan_id),
        
        console.log('Data to be sent:', data);
        const response = await this.orm.call('mfd.installment.receipt', "register_pos_mfd_payment", [data]);
        
        try {
            // const response = await this.orm.call('mfd.installment.receipt', "register_pos_mfd_payment", [data]);
            console.log("Response response", response);
            
            if (!response) {
                throw new Error(_t('No data from server'));
            }

            if (!response.success) {
                throw new Error(data.error || _t('Failed to process payment'));
            }

           

            let addedCount = 0;
            const missingProducts = [];
            console.log('Products to add:', response.products);
            
            if (response.products && Array.isArray(response.products)) {
                for (const productData of response.products) {
                    const product = this.pos.db.get_product_by_id(productData.product_id);
                    
                    console.log('Product data:', productData.product_id, productData.quantity, productData.price);
                    console.log('Processing product:', product);
                    let order = this.pos.get_order();
                    
                    if (product) {
                        try {
                            const orderLine = order.add_product(product, {
                                quantity: productData.quantity || 1,
                                price: productData.price || product.lst_price,
                            });
                            
                            if (orderLine) {
                                addedCount++;
                                console.log(`Product added successfully. Total added: ${addedCount}`);
                            }
                        } catch (addError) {
                            console.error('Error adding product:', addError);
                            missingProducts.push(productData.name || `Product ID: ${productData.product_id}`);
                        }
                    console.log(response.partner_id, 'response.partner_id');
                    if (response.partner_id) {
                        console.log(response.partner_id, 'response.partner_id');
                        const  res_partner_id = response.partner_id;
                        // order.set_partner(res_partner_id);
                            const partner = this.pos.db.get_partner_by_id(res_partner_id);
                            // console.log('Partner data:', response.partner_id, partner);

                
                            if (partner) {
                                console.log('Setting partner:', order);
                                order.set_partner(partner);
                        
                            }
            }
                    } else {
                        console.warn(`Product not found in POS database: ${productData.name} (ID: ${productData.product_id})`);
                        missingProducts.push(productData.name || `Product ID: ${productData.product_id}`);
                    }
                }
            }
            

            // FIXED: Proper message handling with correct scope
            let message;
            if (addedCount > 0) {
                message = _t('Added %s products', addedCount);
                
                if (missingProducts.length > 0) {
                    message += _t('\nSome products could not be added: %s', missingProducts.join(', '));
                    this.notification.add(message, { type: 'warning' });
                } else {
                    this.notification.add(message, { type: 'success' });
                }
            } else {
                message = _t('No products could be added');
                this.notification.add(message, { type: 'warning' });
            }

            if (response.security_amount === 'sec_dep') {
                this.notification.add(_t("Security Deposit Paid"), { type: 'info' });
            

            // Handle report printing
                if (response.report_id) {
                    this.report.doAction("microfinance_loan.report_mfd_installment_receipt", [
                        response.report_id,
                    ]);

                    
                    console.log("Printed data", response);
                } else {
                    console.warn("No report ID received, skipping report generation.");
                }
            }

            this.cancel(); // Close the popup after processing

        } catch (error) {
            console.error("Payment processing error:", error);
            this.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: error.message || _t('Payment processing failed'),
            });
        }
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
        this.cancel();
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
        
        try {
            const data = await this.orm.call('mfd.loan.request', "check_loan_ids", [newName]);
            
            if (data.status === 'error') {
                this.popup.add(ErrorPopup, {
                    title: _t("Error"),
                    body: data.body,
                });
            } else if (data.status === 'success') {
                this.popup.add(InstallmentPopup, {
                    loan_ids: data.loan_ids,
                    bank_ids: data.bank_ids
                });
            }
        } catch (error) {
            console.error("Error checking loan IDs:", error);
            this.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: _t('Failed to check loan information'),
            });
        }
    }
}

ProductScreen.addControlButton({
    component: MicrofinanceButton,
});