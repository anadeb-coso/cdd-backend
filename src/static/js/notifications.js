function pushNotify(
    message, 
    type = "error",
    timeout = 10000 // Durée avant disparition en ms
) {
    const notif = document.createElement("div");

    notif.style.background = type === "error" ? "#e74c3c" : "#2ecc71";
    notif.style.color = "#fff";
    notif.style.padding = "12px 18px";
    notif.style.marginTop = "10px";
    notif.style.borderRadius = "8px";
    notif.style.boxShadow = "0 2px 10px rgba(0,0,0,0.3)";
    notif.style.fontSize = "15px";
    notif.style.fontFamily = "Arial";
    notif.style.transform = "translateX(120%)";
    notif.style.transition = "transform 0.5s ease";

    notif.innerHTML = message;

    document.getElementById("push-notification-container").appendChild(notif);

    // Animation entrée
    setTimeout(() => {
        notif.style.transform = "translateX(0)";
    }, 50);

    // Disparition après 4 secondes
    setTimeout(() => {
        notif.style.transform = "translateX(120%)";
        setTimeout(() => notif.remove(), 500);
    }, timeout);
}