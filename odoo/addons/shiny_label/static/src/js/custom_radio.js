/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useInputField } from "@web/views/fields/input_field_hook";
import { Component, useRef } from "@odoo/owl";

export class CustomRadioField extends Component {
    static template = 'CustomRadioFieldTemplate'
    setup() {
        super.setup();
        this.radioInput = useRef('radioInput');
        useInputField({ getValue: () => this.props.value || "", refName: "radioInput" });
    }

    _onChangeRadio(ev) {
        if (this.radioInput.el) {
            this.props.update(this.radioInput.el.value);
        }
    }
}

registry.category("fields").add("custom_radio", CustomRadioField);
