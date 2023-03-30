function set_datas(element, data){
    v = element.val();
    element.html('');
    $(element).next().find('b[role="presentation"]').hide();
    
    let options = '';

    options += '<option value=""></option>';

    $.each(data, function (index, value) {
        let option = '<option value="' + value[0] + '"';
        if(v == value[0]){
            option += ' selected>';
        }else{
            option += '>';
        }
        
        option += value[1] + '</option>';
         options += option
    });
   

    element.html(options);
    element.trigger('change');
    let element_val = element.val();
    if (element_val !== '') {
        element.val(element_val)
    }
}




function ajax_request_cascade(url, id){
    let elment_id_phase = $("#id_phase");
    let elment_id_activity = $("#id_activity");
    let elment_id_task = $("#id_task");
    
    $("#"+id).on("change keyup", function () {
        $(this).attr('disabled', true);
        $.ajax({
            type: 'GET',
            url: url,
            data: {
                phase_name: elment_id_phase.val(),
                activity_name: elment_id_activity.val(),
                task_name: elment_id_task.val()
            },
            success: function (data) {
                if(id == "id_phase"){
                    set_datas(elment_id_activity, data.activities);
                    set_datas(elment_id_task, data.tasks);
                }else if(id == "id_activity"){
                    set_datas(elment_id_task, data.tasks);
                }
                
            },
            error: function (data) {
                alert(error_server_message + "Error " + data.status);
                $(".filter_fields select").attr('disabled', false);
            }
        }).done(function () {
                $(".filter_fields select").attr('disabled', false);
            }
        );

    });
}





function set_datas_administrative_level(element, data){
    v = element.val();
    element.html('');
    $(element).next().find('b[role="presentation"]').hide();
    
    let options = '';

    options += '<option value=""></option>';

    $.each(data, function (index, value) {
        let option = '<option value="' + value.administrative_id + '"';
        if(v == value.name){
            option += ' selected>';
        }else{
            option += '>';
        }
        
        option += value.name + '</option>';
        options += option
    });


    element.html(options);
    element.trigger('change');
    let element_val = element.val();
    if (element_val !== '') {
        element.val(element_val)
    }
}

function ajax_request_cascade_administrative_level(url, id){
    let elment_id_prefecture = $("#id_prefecture");
    let elment_id_commune = $("#id_commune");
    let elment_id_canton = $("#id_canton");
    let elment_id_village = $("#id_village");
    
    $(".facilitators-filter select").attr('disabled', true);
    $.ajax({
        type: 'GET',
        url: url,
        data: {
            parent_id: $("#"+id).val()
        },
        success: function (data) {
            if(id == "id_region"){
                set_datas_administrative_level(elment_id_prefecture, data.prefectures);
                set_datas_administrative_level(elment_id_commune, data.communes);
                set_datas_administrative_level(elment_id_canton, data.cantons);
                set_datas_administrative_level(elment_id_village, data.villages);
            }else if(id == "id_prefecture"){
                set_datas_administrative_level(elment_id_commune, data.communes);
                set_datas_administrative_level(elment_id_canton, data.cantons);
                set_datas_administrative_level(elment_id_village, data.villages);
            }else if(id == "id_commune"){
                set_datas_administrative_level(elment_id_canton, data.cantons);
                set_datas_administrative_level(elment_id_village, data.villages);
            }else if(id == "id_canton"){
                set_datas_administrative_level(elment_id_village, data.villages);
            }
            $(".facilitators-filter select").attr('disabled', false);
        },
        error: function (data) {
            alert(error_server_message + "Error " + data.status);
            // $(".facilitators-filter select").attr('disabled', false);
        }
    }).done(function () {
            
        }
    );

}