function deselectableRadios(id_input) {
    let rootElement = document;
    if (!window.radioChecked) window.radioChecked = {};
    window.radioClick = function (e) {
        const obj = e.target, name = obj.name || "unnamed";
        if (e.keyCode) return obj.checked = e.keyCode != 32;
        obj.checked = window.radioChecked[name] != obj;
        window.radioChecked[name] = obj.checked ? obj : null;
    };
    rootElement.querySelectorAll("#" + id_input + " input[type='radio']").forEach(radio => {
        radio.setAttribute("onclick", "radioClick(event)");
        radio.setAttribute("onkeyup", "radioClick(event)");
    });
}
