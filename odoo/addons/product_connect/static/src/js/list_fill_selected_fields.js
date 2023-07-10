/** @odoo-module alias=product_connect.ListRenderer **/
import { ListRenderer } from "@web/views/list/list_renderer";
import { patch } from "@web/core/utils/patch";



const { onMounted, onWillStart, useExternalListener } = owl;

patch(ListRenderer.prototype, 'product_connect.ListRenderer', {


  // Add a lifecycle hook to add the event listener
  setup() {
    this._super.apply(this, arguments);
    useExternalListener(window, 'keydown', this.fillSelected);
    useExternalListener(window, 'click', this.onFieldClick);
  },

  onFieldClick(ev) {
    const fieldOuterHTML = ev.target.outerHTML
    const regex = /name="(\S*)"/;
    const clickedFieldName = fieldOuterHTML.match(regex);
    if (clickedFieldName) {
      this.clickedFieldName = clickedFieldName[1];
    }
  },


  async fillSelected(ev) {
    if (ev.key.toLowerCase() !== 'f' || !ev.shiftKey || !ev.metaKey) {
      return;
    }
    const activeRecordId = this.props.list.editedRecord.resId;
    let activeField = this.activeElement?.activeElement?.parentElement?.attributes?.name?.value;
    if (!activeField) {
      activeField = this.clickedFieldName;
    }

    if (!activeField || !activeRecordId) {
      return;
    }
    const selectedRecords = this.props.list.selection.map(record => record.resId);
    if (selectedRecords.length === 0) {
      return;
    }
    const modelName = this.props.list.resModel;

    document.body.click();
    await this.props.list.editedRecord.save();
    const rpc = this.env.services.rpc;
    await rpc('/web/dataset/call_kw', {
      model: 'ir.model',
      method: 'fill_selected_fields',
      args: [[],
        modelName,
        activeField,
        selectedRecords,
        activeRecordId,
      ],
      kwargs: {},
    });
    this.props.list.model.load();
  },

});

