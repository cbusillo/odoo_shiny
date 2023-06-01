console.error("loaded")
odoo.define('shiny_checklist.ListRenderer', function (require) {
    "use strict";

    var ListRenderer = require('web.ListRenderer');

    ListRenderer.include({
        _onFieldChanged: function (ev) {
            console.error("clicked")
            ListRenderer.prototype._onCellClick.apply(this, arguments);

            var $td = $(ev.currentTarget);
            var $tr = $td.parent();
            var fieldIndex = $tr.children().index($td);
            var field = this.columns[fieldIndex];
            if (field.widget === 'many2one') {
                var recordId = $tr.data('id');
                var record = this.state.data.find((r) => r.id === recordId);
                this.trigger_up('edit_line', { recordID: record.id });
                this.trigger_up('edit_autocomplete', { recordID: record.id });
            }
        },
    });
});
