/* @odoo-module */

import { FormRenderer } from "@web/views/form/form_renderer";
import { ListController } from "@web/views/list/list_controller";
import { FormController } from "@web/views/form/form_controller";
import { session } from "@web/session";
import { patch } from "@web/core/utils/patch";
import { jsonrpc } from "@web/core/network/rpc_service";
import { useService } from "@web/core/utils/hooks";

import { onMounted } from "@odoo/owl";

patch(FormRenderer.prototype, {
  setup() {
    super.setup();
    this.orm = useService("orm");
    const self = this;

    return Promise.resolve(super.setup()).then(function (ev) {
      var hash = window.location.hash.substring(1);
      hash = JSON.parse(
        '{"' + hash.replace(/&/g, '","').replace(/=/g, '":"') + '"}',
        function (key, value) {
          return key === "" ? value : decodeURIComponent(value);
        }
      );
      if (hash?.cids || session?.user_companies?.current_company) {
        self.orm
          .call("access.management", "get_chatter_hide_details", [
            session.user_id,
            hash?.cids
              ? parseInt(hash.cids.charAt(0))
              : session.user_companies.current_company,
            hash.model,
          ])
          .then(function (result) {
            if (!result["hide_send_mail"]) {
              var btn1 = setInterval(function () {
                if ($(".o-mail-Chatter-sendMessage").length) {
                  $(".o-mail-Chatter-sendMessage").remove();
                  clearInterval(btn1);
                }
              }, 50);
            }
            if (!result["hide_log_notes"]) {
              var btn2 = setInterval(function () {
                if ($(".o-mail-Chatter-logNote").length) {
                  $(".o-mail-Chatter-logNote").remove();
                  clearInterval(btn2);
                }
              }, 50);
            }
            if (!result["hide_schedule_activity"]) {
              var btn3 = setInterval(function () {
                if ($(".o-mail-Chatter-activity").length) {
                  $(".o-mail-Chatter-activity").remove();
                  clearInterval(btn3);
                }
              }, 50);
            }
          });
      }
    });
  },
});
