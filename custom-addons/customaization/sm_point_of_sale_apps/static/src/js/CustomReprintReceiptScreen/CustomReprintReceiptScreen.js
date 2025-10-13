/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { ReprintReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/reprint_receipt_screen";

patch(ReprintReceiptScreen.prototype, {
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
    async A4TryRePrintReceipt() {
        var receiptHtml = $('.pos_receipt_html').html();
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
    }
});