/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { CustomChequeButtonPopup } from "@sm_point_of_sale_apps/js/CustomChequeButtonPopup/CustomChequeButtonPopup";
import FeedbackPopup from "@pos_customer_feedback/js/feedback_popup"
import CustomerFeedback from "@pos_customer_feedback/js/customer_feedback"
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";

patch(PaymentScreen.prototype, {
    amountToWords(amount) {
        const ones = [
            "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
            "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"
        ];
        const tens = [
            "", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"
        ];
        const thousands = ["", "Thousand", "Million", "Billion"];

        if (amount === 0) {
            return "Zero";
        }
        function convert(num) {
            if (num === 0) {
                return "";
            } else if (num < 20) {
                return ones[num];
            } else if (num < 100) {
                return tens[Math.floor(num / 10)] + (num % 10 ? " " + ones[num % 10] : "");
            } else {
                return ones[Math.floor(num / 100)] + " Hundred" + (num % 100 ? " " + convert(num % 100) : "");
            }
        }
        let result = "";
        let i = 0;
        while (amount > 0) {
            let chunk = amount % 1000;
            if (chunk) {
                result = convert(chunk) + (thousands[i] ? " " + thousands[i] : "") + (result ? " " + result : "");
            }
            amount = Math.floor(amount / 1000);
            i++;
        }
        return result.trim();
    },
    DateFormat(datetime) {
        var dateStr = datetime;
        var [day, month, year] = dateStr.split(' ')[0].split('/');
        var dateObj = new Date(`${year}-${month}-${day}`);
        var dd = String(dateObj.getDate()).padStart(2, '0');
        var mm = String(dateObj.getMonth() + 1).padStart(2, '0');
        var yyyy = dateObj.getFullYear();
        var formattedDate = `${dd}-${mm}-${yyyy}`;
        return formattedDate;
    },
    FormatCurrencyAmount(amount) {
        const formattedAmount = this.env.utils.formatCurrency(amount);
        return formattedAmount;
    },
    TemplateLoad() {
        var pos_order = this.pos.get_order().export_for_printing();
        var company = pos_order.headerData.company;
        var order = pos_order;
        var partner = pos_order.partner;
        var lines = pos_order.orderlines;
        var date_format = this.DateFormat(order.date);
        var format_currency_amount_zero = this.FormatCurrencyAmount(0);
        var format_currency_amount = this.FormatCurrencyAmount(order.amount_total);
        var amount_to_words = this.amountToWords(order.amount_total);
        var company_id = company.id;
        var not_amount_total = ''
        if (!order.comment_feedback) {
            if(order.amount_total) {
                not_amount_total =  format_currency_amount;
            }
            else {
                not_amount_total =  format_currency_amount_zero;
            }
        }
        else {
            not_amount_total =  format_currency_amount_zero;
        }

        console.log('Bang Bang');
        console.log(pos_order);

        var cheque_date = '';
        var comment_feedback = '';
        var customer_feedback = '';
        var amount_total = '';
        if(order.comment_feedback) {
            if(order.date) {
                cheque_date = date_format;
            }
            else {
                cheque_date = '-';
            }
            if(order.customer_feedback) {
                customer_feedback = order.customer_feedback;
            }
            else {
                customer_feedback = '-';
            }
            if(order.comment_feedback) {
                comment_feedback = order.comment_feedback;
            }
            else {
                comment_feedback = '-';
            }
            if(order.amount_total) {
                amount_total = order.amount_total;
            }
            else {
                amount_total = format_currency_amount_zero;
            }
        }
        else {
            cheque_date = '-';
            comment_feedback = '-';
            customer_feedback = '-';
            amount_total = format_currency_amount_zero;
        }
        var lines_list = '';
        for(var i = 0; i < lines.length; i++) {
            lines_list +=`
                <tr>
                    <td class="w-full text-left">
                        ${lines[i].productName ? lines[i].productName : '-'}
                    </td>
                    <td class="w-full text-right">
                        ${lines[i].qty ? lines[i].qty : '-'}
                    </td>
                    <td class="w-full text-right">
                        ${lines[i].unitPrice ? lines[i].unitPrice : '-'}
                    </td>
                    <td class="w-full text-right">
                        ${lines[i].price ? lines[i].price : '-'}
                    </td>
                </tr>
            `;
        }
        var html = `
            <div class="pos_receipt_html pos_receipt" style="width: 1200px; max-width: 1200px;">
                <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.2/dist/css/bootstrap.min.css" />
                <style>
                    .row {
                        display: -webkit-box;
                        display: flex;
                    }
                    body {
                        font-family: Arial, sans-serif;
                    }
                    h1{
                        font-size: 1.5em;
                        color: #222;
                    }
                    h2{
                        font-size: .9em;
                    }
                    h3{
                        font-size: 1.2em;
                        font-weight: 300;
                        line-height: 2em;
                    }
                    p{
                        font-size: .7em;
                        color: #666;
                        line-height: 1.2em;
                    }
                    .info h2 {
                        font-size: 20px;
                    }
                    .div-box {
                        display: flex;
                        flex-direction: row;
                        flex-wrap: nowrap;
                        justify-content: space-between;
                        align-items: center;
                    }
                    .text-transform {
                        text-transform: uppercase;
                        margin-top: 15px;
                        margin-bottom: 0px;
                    }
                    .row-new {
                        flex-direction: row;
                        flex-wrap: nowrap;
                        justify-content: space-between;
                        align-items: flex-start;
                    }
                    .table-bordered {
                        border: 2px solid #000000 !important;
                    }
                    .table thead th {
                        border-bottom: 2px solid #000000;
                    }
                    .table-bordered td, .table-bordered th {
                        border: 2px solid #000000;
                    }
                    .w-full {
                        width: 25% !important;
                    }
                    tfoot tr th {
                        border-top: 2px solid #000000 !important;
                        border-left: inherit !important;
                        border-right: inherit !important;
                        border-bottom: inherit !important;
                    }
                    tfoot tr td {
                        border-top: 2px solid #000000 !important;
                        border-left: inherit !important;
                        border-right: inherit !important;
                        border-bottom: inherit !important;
                    }
                    .text-left {
                        text-align: left;
                    }
                    .text-right {
                        text-align: right;
                    }
                    .service_margin {
                        margin-left: 15px;
                        margin-right: 15px;
                    }
                    .table-bordered {
                        border: inherit;
                    }
                </style>
                <center id="top">
                    <div class="logo">
                        <t t-if="company.id">
                            <img t-attf-src='/web/image?model=res.company&amp;id=${company_id}&amp;field=logo' alt="Logo" class="pos-receipt-logo"/>
                        </t>
                    </div>
                    <div class="info">
                        <h2>
                            ${company.name ? company.name : ''}
                        </h2>
                        <p style="margin-bottom: 6px;font-size: 12px;font-weight: 500;color: #000000;">
                            ${company.email ? company.email : ''}
                        </p>
                        <p style="margin-bottom: 6px;font-size: 12px;font-weight: 500;color: #000000;">
                            ${company.phone ? company.phone : ''}
                        </p>
                        <p style="margin-bottom: 6px;font-size: 12px;font-weight: 500;color: #000000;">
                            ${company.street ? company.street : ''} ${company.street2 ? company.street2 : ''} ${company.city ? company.city : ''} ${company.state_id ? company.state_id[1] : ''} ${company.country_id ? company.country_id[1] : ''} ${company.zip ? company.zip : ''}
                        </p>
                        <p style="margin-bottom: 6px;font-size: 12px;font-weight: 500;color: #000000;">
                            ${company.website ? company.website : ''}
                        </p>
                    </div>
                </center>
                <hr class="service_margin" style="border-top: 2px solid #000000;margin-bottom: 0px;"/>
                <div class="div-box service_margin">
                    <h1 class="text-transform">Donation Receipt</h1>
                    <h1 class="text-transform">
                        ${company.name ? company.name : ''} ${company.city ? '('+company.city+')' : ''}
                    </h1>
                </div>
                <div class="row row-new service_margin" style="margin-top: 20px;margin-bottom: 20px;border: 2px solid #000;padding: 15px;">
                    <div class="col-lg-6">
                        <div class="row row-new">
                            <div class="col-lg-4">
                                <h4 style="font-size: 18px;">Receipt #:</h4>
                            </div>
                            <div class="col-lg-8">
                                <h4 style="font-weight: 500;font-size: 18px;">
                                    ${order.name ? order.name : '-'}
                                </h4>
                            </div>
                        </div>
                        <div class="row row-new">
                            <div class="col-lg-4">
                                <h4 style="font-size: 18px;">Receipt Date #:</h4>
                            </div>
                            <div class="col-lg-8">
                                <h4 style="font-weight: 500;font-size: 18px;">
                                    ${order.date ? date_format : '-'}
                                </h4>
                            </div>
                        </div>
                        <div class="row row-new">
                            <div class="col-lg-4">
                                <h4 style="font-size: 18px;">Donar Name:</h4>
                            </div>
                            <div class="col-lg-8">
                                <h4 style="font-weight: 500;font-size: 18px;">
                                    ${partner.name ? partner.name : '-'}
                                </h4>
                            </div>
                        </div>
                        <div class="row row-new">
                            <div class="col-lg-4">
                                <h4 style="font-size: 18px;">Cell #:</h4>
                            </div>
                            <div class="col-lg-8">
                                <h4 style="font-weight: 500;font-size: 18px;">
                                    ${partner.mobile ? partner.mobile : partner.phone ? partner.phone : '-'}
                                </h4>
                            </div>
                        </div>
                        <div class="row row-new">
                            <div class="col-lg-4">
                                <h4 style="font-size: 18px;">Cash Amount:</h4>
                            </div>
                            <div class="col-lg-8">
                                <h4 style="font-weight: 500;font-size: 18px;">
                                    ${not_amount_total}
                                </h4>
                            </div>
                        </div>
                        <div class="row row-new">
                            <div class="col-lg-4">
                                <h4 style="font-size: 18px;">Remarks:</h4>
                            </div>
                            <div class="col-lg-8">
                                <h4 style="font-weight: 500;font-size: 18px;">-</h4>
                            </div>
                        </div>
                    </div>
                    <div class="col-lg-6">
                        <div class="row row-new">
                            <div class="col-lg-4">
                                <h4 style="font-size: 18px;">Cheque Date:</h4>
                            </div>
                            <div class="col-lg-8">
                                <h4 style="font-weight: 500;font-size: 18px;">
                                    ${cheque_date}
                                </h4>
                            </div>
                        </div>
                        <div class="row row-new">
                            <div class="col-lg-4">
                                <h4 style="font-size: 18px;">Cheque #:</h4>
                            </div>
                            <div class="col-lg-8">
                                <h4 style="font-weight: 500;font-size: 18px;">
                                    ${customer_feedback}
                                </h4>
                            </div>
                        </div>
                        <div class="row row-new">
                            <div class="col-lg-4">
                                <h4 style="font-size: 18px;">Bank Branch #:</h4>
                            </div>
                            <div class="col-lg-8">
                                <h4 style="font-weight: 500;font-size: 18px;">
                                    ${comment_feedback}
                                </h4>
                            </div>
                        </div>
                        <div class="row row-new">
                            <div class="col-lg-4">
                                <h4 style="font-size: 18px;">Cheque Amount:</h4>
                            </div>
                            <div class="col-lg-8">
                                <h4 style="font-weight: 500;font-size: 18px;">
                                    ${amount_total}
                                </h4>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="service_margin">
                    <table class="table table-bordered">
                        <thead>
                            <tr>
                                <th style="text-align: center;" class="w-full">Account Title</th>
                                <th style="text-align: center;" class="w-full">Quantity</th>
                                <th style="text-align: center;" class="w-full">Rate</th>
                                <th style="text-align: center;" class="w-full">Amount</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${lines_list}
                        </tbody>
                    </table>
                    <table class="table">
                        <tfoot>
                            <tr>
                                <th class="w-full text-left">Amount In Words:</th>
                                <td class="w-full text-left">
                                    ${order.amount_total ? amount_to_words : '-'}
                                </td>
                                <th class="w-full text-left">Total Amount:</th>
                                <td class="w-full text-right">
                                    ${order.amount_total ? format_currency_amount : format_currency_amount_zero}
                                </td>
                            </tr>
                            <tr>
                                <th style="border-top: inherit !important;" class="w-full text-left">Printed By:</th>
                                <td style="border-top: inherit !important;" class="w-full text-left">
                                    ${order.cashier ? order.cashier : '-'}
                                </td>
                                <th style="border-top: inherit !important;" class="w-full text-left">Entered By:</th>
                                <td style="border-top: inherit !important;" class="w-full text-right">
                                    ${order.cashier ? order.cashier : '-'}
                                </td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
                <br />
                <br />
                <br />
                <br />
                <hr class="service_margin" style="border-top: 2px solid #000000;"/>
                <div class="row row-new service_margin" style="margin-top: 20px;margin-bottom: 20px;border: 2px solid #000;padding: 15px;">
                    <div class="col-lg-6">
                        <div class="row row-new">
                            <div class="col-lg-4">
                                <h4 style="font-size: 18px;">Receipt #:</h4>
                            </div>
                            <div class="col-lg-8">
                                <h4 style="font-weight: 500;font-size: 18px;">
                                    ${order.name ? order.name : '-'}
                                </h4>
                            </div>
                        </div>
                        <div class="row row-new">
                            <div class="col-lg-4">
                                <h4 style="font-size: 18px;">Receipt Date #:</h4>
                            </div>
                            <div class="col-lg-8">
                                <h4 style="font-weight: 500;font-size: 18px;">
                                    ${order.date ? date_format : '-'}
                                </h4>
                            </div>
                        </div>
                        <div class="row row-new">
                            <div class="col-lg-4">
                                <h4 style="font-size: 18px;">Donar Name:</h4>
                            </div>
                            <div class="col-lg-8">
                                <h4 style="font-weight: 500;font-size: 18px;">
                                    ${partner.name ? partner.name : '-'}
                                </h4>
                            </div>
                        </div>
                        <div class="row row-new">
                            <div class="col-lg-4">
                                <h4 style="font-size: 18px;">Cell #:</h4>
                            </div>
                            <div class="col-lg-8">
                                <h4 style="font-weight: 500;font-size: 18px;">
                                    ${partner.mobile ? partner.mobile : partner.phone ? partner.phone : '-'}
                                </h4>
                            </div>
                        </div>
                        <div class="row row-new">
                            <div class="col-lg-4">
                                <h4 style="font-size: 18px;">Cash Amount:</h4>
                            </div>
                            <div class="col-lg-8">
                                <h4 style="font-weight: 500;font-size: 18px;">
                                    ${not_amount_total}
                                </h4>
                            </div>
                        </div>
                        <div class="row row-new">
                            <div class="col-lg-4">
                                <h4 style="font-size: 18px;">A/C Title:</h4>
                            </div>
                            <div class="col-lg-8">
                                <h4 style="font-weight: 500;font-size: 18px;">-</h4>
                            </div>
                        </div>
                    </div>
                    <div class="col-lg-6">
                        <div class="row row-new">
                            <div class="col-lg-4">
                                <h4 style="font-size: 18px;">Receipt By:</h4>
                            </div>
                            <div class="col-lg-8">
                                <h4 style="font-weight: 500;font-size: 18px;">
                                    ${order.cashier ? order.cashier : '-'}
                                </h4>
                            </div>
                        </div>
                        <div class="row row-new">
                            <div class="col-lg-4">
                                <h4 style="font-size: 18px;">Printed By:</h4>
                            </div>
                            <div class="col-lg-8">
                                <h4 style="font-weight: 500;font-size: 18px;">
                                    ${order.cashier ? order.cashier : '-'}
                                </h4>
                            </div>
                        </div>
                        <div class="row row-new">
                            <div class="col-lg-4">
                                <h4 style="font-size: 18px;">Printed Date:</h4>
                            </div>
                            <div class="col-lg-8">
                                <h4 style="font-weight: 500;font-size: 18px;">
                                    ${order.date ? date_format : '-'}
                                </h4>
                            </div>
                        </div>
                        <div class="row row-new">
                            <div class="col-lg-4">
                                <h4 style="font-size: 18px;">Cheque Amount:</h4>
                            </div>
                            <div class="col-lg-8">
                                <h4 style="font-weight: 500;font-size: 18px;">
                                    ${amount_total}
                                </h4>
                            </div>
                        </div>
                        <div class="row row-new">
                            <div class="col-lg-4">
                                <h4 style="font-size: 18px;">Total Amount:</h4>
                            </div>
                            <div class="col-lg-8">
                                <h4 style="font-weight: 500;font-size: 18px;">
                                    ${order.amount_total ? format_currency_amount : format_currency_amount_zero}
                                </h4>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        return html;
    },
    async afterOrderValidation(suggestToSync = true) {
        this.pos.db.remove_unpaid_order(this.currentOrder);
        if (suggestToSync && this.pos.db.get_orders().length) {
            const { confirmed } = await this.popup.add(ConfirmPopup, {
                title: _t("Remaining unsynced orders"),
                body: _t("There are unsynced orders. Do you want to sync these orders?"),
            });
            if (confirmed) {
                this.pos.push_orders();
            }
        }
        let nextScreen = this.nextScreen;
        if (nextScreen === "ReceiptScreen" && !this.currentOrder._printed && this.pos.config.iface_print_auto) {
            const invoiced_finalized = this.currentOrder.is_to_invoice() ? this.currentOrder.finalized : true;
            if (invoiced_finalized) {
                var receiptHtml = this.TemplateLoad();
                var w = window.open();
                if(w) {
                    var style = document.createElement('style');
                    style.innerHTML = document.querySelector('style').innerHTML;
                    w.document.head.appendChild(style);
                    w.document.write(receiptHtml);
                    w.document.close();
                    w.onload = function() {
                        w.print();
                        w.close();
                    };
                }
                if (this.pos.config.iface_print_skip_screen) {
                    this.pos.removeOrder(this.currentOrder);
                    this.pos.add_new_order();
                    nextScreen = "ProductScreen";
                }
            }
        }
        this.pos.showScreen(nextScreen);
    },
    async addNewPaymentLine(paymentMethod) {
        console.log(paymentMethod);

        // if((paymentMethod.name == 'Cheque') || (paymentMethod.name == 'QR Code')) {
        if(paymentMethod.popup == true) {
            const order = this.pos.get_order();
            if (order.partner) {
                if (this.pos.selectedOrder.partner && this.pos.selectedOrder.orderlines){
                    console.log(this.pos.selectedOrder.orderlines);

                    const { confirmed, payload: inputFeedback } = await this.popup.add(FeedbackPopup, {
                        // startingValue: this.pos.get_order().get_comment_feedback(),
                        startingValue: paymentMethod.name,
                        title: _t('Add Cheque') ? paymentMethod.name == 'Cheque' : _t('Add QR Code') ? paymentMethod.name == 'QR Code' : _t(`Add ${paymentMethod.name}`)
                    });
                    if (confirmed) {
                        console.log("inputFeedback",inputFeedback);
                        console.log("inputFeedback",this.pos.selectedOrder);
                        this.pos.selectedOrder.comment_feedback = inputFeedback.commentValue;
                        this.pos.selectedOrder.customer_feedback = inputFeedback.ratingValue;
                        this.pos.selectedOrder.customer_feedback = inputFeedback.bankname;
                    }
                    const result = this.currentOrder.add_paymentline(paymentMethod);
                    if (result) {
                        this.numberBuffer.reset();
                        return true;
                    } else {
                        this.popup.add(ErrorPopup, {
                            title: _t("Error"),
                            body: _t("There is already an electronic payment in progress."),
                        });
                        return false;
                    }
                }
                else {
                    return false;
                }
            }
            else {
                this.popup.add(ErrorPopup, {
                    title: _t("Error"),
                    body: _t("Please Select Customer."),
                });
                return false;
            }
        }
        else {
            const result = await this.currentOrder.add_paymentline(paymentMethod);
            if (result) {
                this.numberBuffer.reset();
                return true;
            } else {
                this.popup.add(ErrorPopup, {
                    title: _t("Error"),
                    body: _t("There is already an electronic payment in progress."),
                });
                return false;
            }
        }
    }
});
