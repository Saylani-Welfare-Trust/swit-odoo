// /** @odoo-module **/

// import {useService} from "@web/core/utils/hooks";
// import {usePos} from "@point_of_sale/app/store/pos_hook";
// import { useState } from "@odoo/owl";

// import {ErrorPopup} from "@point_of_sale/app/errors/popups/error_popup";

// import {AbstractAwaitablePopup} from "@point_of_sale/app/popup/abstract_awaitable_popup";
// import {_t} from "@web/core/l10n/translation";


// export class DisbursementListPopup extends AbstractAwaitablePopup{
//     static template = "bn_welfare.DisbursementListPopup";

//   setup() {
//       const today = new Date();
//       const formattedDate = today.toISOString().split('T')[0];
//       console.log(formattedDate, 'formattedDate')
      
//       const flattenedCollectionIds = this.collection_ids.flat();
//       console.log(flattenedCollectionIds, 'Flat Collection IDs')

//       this.report = useService("report");
//       this.printer = useService("printer");
//       this.pos = usePos();
//       this.popup = useService("popup");
//       this.orm = useService("orm");
//       this.title = 'Create Disbursement Payment';
//       this.disbursement_id = this.props.disbursement_id;
//       this.collection_ids = this.props.collection_ids;
//       this.amount = useState({ amount: '' });
//       this.payment = useState({ payment_type: 'cash' });
//       this.selected_collection_id = useState({ collection_id: flattenedCollectionIds.length > 0 ? flattenedCollectionIds[0].id : '' });
//       this.cheque_number = useState({ number: '' });
//       this.cheque_date = useState({ date: formattedDate });
//       this.notification = useService("notification");
//   }

//   onPaymentMethodChange(event) {
//       this.payment.payment_type = event.target.value;
//   }
//   onAmountChange(event) {
//       this.amount.amount = event.target.value;
//   }
//   onCollectionChange(event) {
//       this.selected_collection_id.collection_id = event.target.value;
//   }
//   onChequeNumberChange(event) {
//       this.cheque_number.number = event.target.value;
//   }
//   onChequeDateChange(event) {
//       this.cheque_date.date = event.target.value;
//   }

//   async confirmDisbursement(){
//       let data ={
//           'payment_type': this.payment.payment_type,
//           'disbursement_id': this.disbursement_id.id,
//           'disbursement_number': disbursement_id.name,
//           'currency_id': this.disbursement_id.currency_id,
//           'amount': this.amount.amount,
//           'collection_id': this.selected_collection_id.collection_id,
//           'cheque_number': this.cheque_number.number,
//           'cheque_date': this.cheque_date.date,
//           'pos_session_id': this.pos.pos_session.id,
//           'res_model': this.disbursement_id.res_model,
//       }
//       console.log("Disbursement Data", data)

//       await this.orm.call('disbursement.request', "mark_as_disbursed", [data]).then((data) => {
//             if (data.status === 'error') {
//                 this.popup.add(ErrorPopup, {
//                     title: _t("Error"),
//                     body: data.body,
//                 });
//             }
//             if (data.status === 'success') {
//                 this.notification.add(_t("Operation Successful"), {
//                     type: "info",
//                 });
//                 this.cancel()
            
//             }
            
//             // this.report.doAction("bn_welfare.disbursement_slip_report_action", [
//             //     data.report_id,
//             // ]);

//             console.log("Printed Disbursement Data", data)
//       })
//   }
// }

// export class DisbursementPopup extends AbstractAwaitablePopup {
//     static template = "bn_welfare.DisbursementPopup";

//     setup() {
//         this.pos = usePos();
//         this.report = useService("report");
//         this.popup = useService("popup");
//         this.orm = useService("orm");
//         this.title = 'Disbursement';
//         this.disbursement_ids = this.props.disbursement_ids;
//         this.collection_ids = this.props.collection_ids;
//         this.notification = useService("notification");
//     }

//     async onClick(disbursement_id) {
//         let data = {
//             'disbursement_id': disbursement_id.id,
//             'disbursement_number': disbursement_id.name,
//             'res_model': disbursement_id.res_model,
//         }
//         console.log("Disbursement Data", data)


//         const response = await this.orm.call('disbursement.request', "mark_as_disbursed", [data]).then((data) => {

//                 try {
//                     // const response = await this.orm.call('mfd.installment.receipt', "register_pos_mfd_payment", [data]);
//                     console.log("Response response", response);
                    
//                     if (!response) {
//                         throw new Error(_t('No data from server'));
//                     }

//                     if (!response.success) {
//                         throw new Error(data.error || _t('Failed to process payment'));
//                     }

                

//                     let addedCount = 0;
//                     const missingProducts = [];
//                     console.log('Products to add:', response.products);
                    
//                     if (response.products && Array.isArray(response.products)) {
//                         for (const productData of response.products) {
//                             const product = this.pos.db.get_product_by_id(productData.product_id);
                            
//                             console.log('Product data:', productData.product_id, productData.quantity, productData.price);
//                             console.log('Processing product:', product);
//                             let order = this.pos.get_order();
                            
//                             if (product) {
//                                 try {
//                                     const orderLine = order.add_product(product, {
//                                         quantity: productData.quantity || 1,
//                                         price: productData.price || product.lst_price,
//                                     });
                                    
//                                     if (orderLine) {
//                                         addedCount++;
//                                         console.log(`Product added successfully. Total added: ${addedCount}`);
//                                     }
//                                 } catch (addError) {
//                                     console.error('Error adding product:', addError);
//                                     missingProducts.push(productData.name || `Product ID: ${productData.product_id}`);
//                                 }
//                             console.log(response.partner_id, 'response.partner_id');
//                             if (response.partner_id) {
//                                 console.log(response.partner_id, 'response.partner_id');
//                                 const  res_partner_id = response.partner_id;
//                                 // order.set_partner(res_partner_id);
//                                     const partner = this.pos.db.get_partner_by_id(res_partner_id);
//                                     // console.log('Partner data:', response.partner_id, partner);

                        
//                                     if (partner) {
//                                         console.log('Setting partner:', order);
//                                         order.set_partner(partner);
                                
//                                     }
//                     }
//                             } else {
//                                 console.warn(`Product not found in POS database: ${productData.name} (ID: ${productData.product_id})`);
//                                 missingProducts.push(productData.name || `Product ID: ${productData.product_id}`);
//                             }
//                         }
//                     }
                    

//                     // FIXED: Proper message handling with correct scope
//                     let message;
//                     if (addedCount > 0) {
//                         message = _t('Added %s products', addedCount);
                        
//                         if (missingProducts.length > 0) {
//                             message += _t('\nSome products could not be added: %s', missingProducts.join(', '));
//                             this.notification.add(message, { type: 'warning' });
//                         } else {
//                             this.notification.add(message, { type: 'success' });
//                         }
//                     } else {
//                         message = _t('No products could be added');
//                         this.notification.add(message, { type: 'warning' });
//                     }

//                     if (response.security_amount === 'sec_dep') {
//                         this.notification.add(_t("Security Deposit Paid"), { type: 'info' });
                    

//                     // Handle report printing
//                         if (response.report_id) {
//                             this.report.doAction("bn_welfare.disbursement_slip_report_action", [
//                                 response.report_id,
//                             ]);

                            
//                             console.log("Printed data", response);
//                         } else {
//                             console.warn("No report ID received, skipping report generation.");
//                         }
//                     }

//                     this.cancel(); // Close the popup after processing

//                 } catch (error) {
//                     console.error("Payment processing error:", error);
//                     this.popup.add(ErrorPopup, {
//                         title: _t("Error"),
//                         body: error.message || _t('Payment processing failed'),
//                     });
//                 }
//     }


//     )}
// }


        



/** @odoo-module **/

import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useState } from "@odoo/owl";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { _t } from "@web/core/l10n/translation";

export class DisbursementListPopup extends AbstractAwaitablePopup {
    static template = "bn_welfare.DisbursementListPopup";

    setup() {
        const today = new Date();
        const formattedDate = today.toISOString().split('T')[0];
        console.log(formattedDate, 'formattedDate');
        
        const flattenedCollectionIds = this.collection_ids.flat();
        console.log(flattenedCollectionIds, 'Flat Collection IDs');

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
        this.selected_collection_id = useState({ 
            collection_id: flattenedCollectionIds.length > 0 ? flattenedCollectionIds[0].id : '' 
        });
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

    async confirmDisbursement() {
        let data = {
            'payment_type': this.payment.payment_type,
            'disbursement_id': this.disbursement_id.id,
            'disbursement_number': this.disbursement_id.name,
            'currency_id': this.disbursement_id.currency_id,
            'amount': this.amount.amount,
            'collection_id': this.selected_collection_id.collection_id,
            'cheque_number': this.cheque_number.number,
            'cheque_date': this.cheque_date.date,
            'pos_session_id': this.pos.pos_session.id,
            'res_model': this.disbursement_id.res_model,
        };
        console.log("Disbursement Data", data);

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
                this.cancel();
            }
            
            // this.report.doAction("bn_welfare.disbursement_slip_report_action", [
            //     data.report_id,
            // ]);

            console.log("Printed Disbursement Data", data);
        });
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
        let data = {
            'disbursement_id': disbursement_id.id,
            'disbursement_number': disbursement_id.name,
            'res_model': disbursement_id.res_model,
        };
        console.log("Disbursement Data", data);

        // FIXED: Properly await the response and use the returned data
        const response = await this.orm.call('disbursement.request', "mark_as_disbursed", [data]);
        console.log("Response data", response);
        
        if (!response) {
            throw new Error(_t('No data from server'));
        }

        if (response.status === 'error') {
            this.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: response.body,
            });
            return;
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
                            lst_price: productData.price ,
                        });
                        
                        if (orderLine) {
                            addedCount++;
                            console.log(`Product added successfully. Total added: ${addedCount}`);
                            console.log(response.partner_id, 'response.partner_id');
                            if (response.partner_id) {
                                console.log(response.partner_id, 'response.partner_id');

                                const partner = this.pos.db.get_partner_by_id(response.partner_id);
                                console.log('Partner data:',  partner);
                                order.set_partner(partner);
                                
                                // if (partner) {
                                //     console.log('Setting partner:', order);
                                //     order.set_partner(partner);
                                // }
                            }



                        }
                    } catch (addError) {
                        console.error('Error adding product:', addError);
                        missingProducts.push(productData.name || `Product ID: ${productData.product_id}`);
                    }
                    
                    
                } else {
                    console.warn(`Product not found in POS database: ${productData.name} (ID: ${productData.product_id})`);
                    missingProducts.push(productData.name || `Product ID: ${productData.product_id}`);
                }
            }
        }

        // Handle success notification
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

        if (response.status === 'success') {
            console.log("Printed data", response);
        
            // Handle report printing
            if (response.report_id) {
                // this.report.doAction("bn_welfare.disbursement_slip_report_action", [
                //     response.report_id,
                // ]);
                console.log("Printed data", response);
            } else {
                console.warn("No report ID received, skipping report generation.");
            }
        }

        if (response.status === 'success') {
            this.notification.add(_t("Record has been Disbursed Successfully"), {
                type: "info",
            });
        }

        this.cancel(); // Close the popup after processing
        // try {

        // } catch (error) {
        //     console.error("Payment processing error:", error);
        //     this.popup.add(ErrorPopup, {
        //         title: _t("Error"),
        //         body: error.message || _t('Payment processing failed'),
        //     });
        // }
    }
}













































// //             if (data.status === 'error') {
// //                 this.popup.add(ErrorPopup, {
// //                     title: _t("Error"),
// //                     body: data.body,
// //                 });
// //             }
// //             if (data.status === 'success') {
// //                 this.notification.add(_t("Record has been Disbursed Successful"), {
// //                     type: "info",
// //                 });
// //                 this.cancel()
// //             }
  
// //             // this.report.doAction("bn_welfare.disbursement_slip_report_action", [
// //             //     data.report_id,
// //             // ]);

// //             console.log("Printed Disbursement Data", data)
// //         })
//     // }
// //  }