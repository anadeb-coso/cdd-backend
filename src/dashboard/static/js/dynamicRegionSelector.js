let ancestors = [];

function changeRegionTrigger(url, placeholder) {
    $(document).on("change", ".region", function () {
        $("#id_administrative_region_value").val($("select.region:last").val());
        loadNextLevelRegions($(this), url, placeholder);
    });
}

function loadNextLevelRegions(current_level, url, placeholder) {
    let current_level_val = current_level.val();
    console.log('current_level_val para cargar proximo selector: ' + current_level_val);
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
                    let id_select = 'id_' + data[0].administrative_level;
                    let label = data[0].administrative_level.replace(/^\w/, (c) => c.toUpperCase());
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
                        let option = '<option value="' + administrative_id;
                        if (ancestors.includes(administrative_id)) {
                            option += '" selected="selected">';
                            ancestors = ancestors.filter(function (ancestor) {
                                return ancestor !== administrative_id;
                            });
                        } else {
                            option += '">';
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
                    $('#next').prop('disabled', false);
                }
            }
        );
    } else {
        let next_selects = current_level.closest('.form-group').nextAll('.dynamic-select');
        $.each(next_selects, function (index, select) {
            select.remove();
        });
    }
}

function loadRegionSelectors(url) {
    let administrative_region_value = $("#id_administrative_region_value").val();
    $.ajax({
        type: 'GET',
        url: url,
        data: {
            administrative_id: administrative_region_value,
        },
        success: function (data) {
            if (data.length > 0) {
                data = data.slice(1);
                data.push(administrative_region_value);
                ancestors = data;
                loadNextLevelRegions($("select.region:last"), get_choices_url, choice_placeholder);
            } else {
                $('#next').prop('disabled', false);
            }
        },
        error: function (data) {
            alert(error_server_message + "Error " + data.status);
        }
    });
}
