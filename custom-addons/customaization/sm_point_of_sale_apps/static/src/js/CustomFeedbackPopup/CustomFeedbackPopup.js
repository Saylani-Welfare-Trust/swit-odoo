/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import FeedbackPopup from "@pos_customer_feedback/js/feedback_popup"

patch(FeedbackPopup.prototype, {
    async RatingChange(ev) {
        if (!isNaN(parseInt(ev.target.value))) {
            this.state.ratingValue = ev.target.value;
            const starTotal = 5;
            const starPercentage = (this.state.ratingValue / starTotal) * 100;
            const starPercentageRounded = `${(Math.round(starPercentage / 10) * 10)}%`;
            if(document.querySelector(`.stars-inner`)) {
                document.querySelector(`.stars-inner`).style.width = starPercentageRounded;
            }

        }
    }
});

