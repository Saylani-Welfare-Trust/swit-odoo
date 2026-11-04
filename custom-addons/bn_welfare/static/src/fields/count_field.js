/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useState } from "@odoo/owl";
import { parseInteger } from "@web/views/fields/parsers";
import { useInputField } from "@web/views/fields/input_field_hook";
import { useNumpadDecimal } from "@web/views/fields/numpad_decimal_hook";
import { IntegerField, integerField } from "@web/views/fields/integer/integer_field";

/**
 * Integer field that tells the user why the value is refused,
 * instead of only turning red. Same setup as IntegerField, with its own parse.
 */
export class CountField extends IntegerField {
    setup() {
        this.notification = useService("notification");
        this.state = useState({
            hasFocus: false,
        });
        useInputField({
            getValue: () => this.formattedValue,
            refName: "numpadDecimal",
            parse: (v) => this.parse(v),
        });
        useNumpadDecimal();
    }

    parse(value) {
        try {
            return parseInteger(value);
        } catch (error) {
            const label = this.props.record.fields[this.props.name].string;
            this.notification.add(
                _t("%s: only numbers are allowed, you can't use alphabets.", label),
                { type: "danger" }
            );
            throw error;
        }
    }
}

export const countField = {
    ...integerField,
    component: CountField,
};

registry.category("fields").add("welfare_count", countField);
