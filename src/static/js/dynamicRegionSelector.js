let ancestors = [];
let selected_regions = [];
let selected_regions_json = [];

$("#id_administrative_level").val(null).trigger('change.select2');

function toggleAddButton() {
    if ($("select.region:last").val()) {
        $('#add').removeClass('disabled');
    } else {
        $('#add').addClass('disabled');
    }
}

function toggleSubmitButton() {
    if (selected_regions.length > 0) {
        $('#submit').prop('disabled', false);
    } else {
        $('#submit').prop('disabled', true);
        toggleAddButton();
    }
}

function changeRegionTrigger(url, placeholder) {
    $(document).on("change", ".region", function () {
        loadNextLevelRegions($(this), url, placeholder);
    });
}

$(document).on("click", "#add", function () {
    let selected_region = $("select.region:last");
    let administrative_id = selected_region.val();
    if(administrative_id && administrative_id !== "0" && administrative_id !== 0){
        selected_regions.push(administrative_id);
        let region_name = $('#' + selected_region[0].id + ' option:selected').text();
        let selected_region_json = {
            "name": region_name,
            "id": administrative_id
        };
        selected_regions_json.push(selected_region_json);
        $("#id_administrative_levels").val(JSON.stringify(selected_regions_json));
        $(this).addClass('disabled');
        $('#' + administrative_id).prop('disabled', true);
        let region_long_name = $("select.region").map(function () {
            return this.options[this.selectedIndex].text;
        }).get().reverse().join(", ");
        let region_html = "<a class='tag mt-2' >" +
            "<i value='" + administrative_id + "' class='fa fa-remove mr-2 link remove-region' title='Remove'></i>" +
            region_long_name + "</a>";
        $("#selected_regions").append(region_html);
        toggleSubmitButton();
    }
});

$(document).on("click", ".remove-region", function () {
    let administrative_id = $(this).attr('value');
    $(this).parent().remove();
    $('#' + administrative_id).prop('disabled', false);
    selected_regions = $.grep(selected_regions, function (e) {
        return e !== administrative_id;
    });
    selected_regions_json = $.grep(selected_regions_json, function (e) {
        return e.id !== administrative_id;
    });
    $("#id_administrative_levels").val(JSON.stringify(selected_regions_json));
    toggleSubmitButton();
});

function loadNextLevelRegions(current_level, url, placeholder) {
    let current_level_val = current_level.val();
    //console.log('current_level_val para cargar proximo selector: ' + current_level_val);
    if (current_level_val !== '') {
        let select_region = $(".region");
        select_region.attr('disabled', true);
        $.ajax({
            type: 'GET',
            url: url,
            data: {
                parent_id: current_level_val,
            },
            success: function (data) {
                if (data.length > 0) {
                    let id_select = 'id_' + slugify(data[0].administrative_level, '_');
                    let label = data[0].administrative_level.toUpperCase();
                    let child;
                    let new_input = document.createElement('div');
                    new_input.className = 'form-group row dynamic-select';

                    let label_element = document.createElement('label');
                    label_element.className = 'col-md-3 col-form-label';
                    label_element.setAttribute('for', id_select);
                    label_element.innerHTML = label;
                    new_input.appendChild(label_element);

                    let div_element = document.createElement('div');
                    div_element.className = 'col-md-9';

                    let select_element = document.createElement('select');
                    select_element.className = 'form-control region';
                    select_element.setAttribute("required", "");
                    select_element.setAttribute('id', id_select);
                    div_element.appendChild(select_element);

                    new_input.appendChild(div_element);

                    current_level.parent().parent().after(new_input);
                    child = current_level.closest('.form-group').next().find('.region');
                    child.select2({
                        allowClear: true,
                        placeholder: placeholder,
                    });
                    $(child).next().find('b[role="presentation"]').hide();
                    $(child).next().find('.select2-selection__arrow').append(
                        '<i class="fas fa-chevron-circle-down text-primary" style="margin-top:12px;"></i>');

                    let options = '<option value></option>';
                    $.each(data, function (index, value) {
                        let administrative_id = value.administrative_id;
                        let option = '<option id="' + administrative_id + '" value="' + administrative_id + '"';
                        if (selected_regions.includes(administrative_id)) {
                            option += ' disabled ';
                        }
                        if (ancestors.includes(administrative_id)) {
                            option += ' selected="selected">';
                            ancestors = ancestors.filter(function (ancestor) {
                                return ancestor !== administrative_id;
                            });
                        } else {
                            option += '>';
                        }
                        option += value.name + '</option>';
                        options += option

                    });
                    child.html(options);
                    child.trigger('change');
                    let child_val = child.val();
                    if (child_val !== '') {
                        child.val(child_val)
                    }
                }
            },
            error: function (data) {
                alert(error_server_message + "Error " + data.status);
            }
        }).done(function () {
                if (ancestors.length <= 1) {
                    select_region.attr('disabled', false);
                }
                toggleAddButton();
            }
        );
    } else {
        let next_selects = current_level.closest('.form-group').nextAll('.dynamic-select');
        $.each(next_selects, function (index, select) {
            select.remove();
        });
        toggleAddButton();
    }
}

function loadRegionSelectors(url) {
    let administrative_levels = $("#id_administrative_levels").val();
    $.ajax({
        type: 'GET',
        url: url,
        data: {
            administrative_id: administrative_levels,
        },
        success: function (data) {
            if (data.length > 0) {
                data = data.slice(1);
                data.push(administrative_levels);
                ancestors = data;
                loadNextLevelRegions($("select.region:last"), get_choices_url, choice_placeholder);
            }
        },
        error: function (data) {
            alert(error_server_message + "Error " + data.status);
        }
    });
}
