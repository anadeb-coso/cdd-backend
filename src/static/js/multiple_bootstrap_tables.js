

jQuery.extend(jQuery.fn.dataTableExt.oSort, {
    "numeric-comma-pre": function (a) {
        var x = parseFloat(a.replace(/\s+/g, '').replace(',', '.')); // Remove spaces and replace comma with dot
        return isNaN(x) ? 0 : x;
    },
    "numeric-comma-asc": function (a, b) {
        return a - b;
    },
    "numeric-comma-desc": function (a, b) {
        return b - a;
    }
});

function multiple_bootstrap_tables (ids_tables_custom, dom='Blrtip', columnDefs_numeric_order={}){
    // dom = 'Blrtip' | 'Blfrtip'
    // columnDefs_numeric_order = {id_table_custom : [0, 5, 6, 8]}

    let id_table_custom;
    const table_stats = {};
    for(var i=0; i<ids_tables_custom.length; i++){
        id_table_custom = ids_tables_custom[i];
        
        if ($.fn.DataTable.isDataTable(`#${id_table_custom}`)) {
            $(`#${id_table_custom}`).DataTable().destroy();
            $(`#${id_table_custom}`).empty(); 
        }

        table_stats[id_table_custom] = $(`#${id_table_custom}`).DataTable({
            autoWidth: false,
            responsive: true,
            scrollX: false,
            columnDefs: [
                { 
                    type: 'numeric-comma', targets: columnDefs_numeric_order[id_table_custom] ?? []
                }
            ],
            dom: dom,
            buttons: ['copy', 'excel', 'pdf', 'colvis'],
            lengthMenu: [10, 20, 30, 40, 43, 50, 60, 70, 80, 90, 100],
            pageLength: 10,
            order: []
        });
        // $(`#${id_table_custom}-search`).on('keyup', function () {
        //     table_stats[id_table_custom].search($(this).val()).draw();
        // });
    }
}

