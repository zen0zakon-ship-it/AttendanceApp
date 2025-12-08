// static/js/student.js

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("mark-form");
  const btn = document.getElementById("mark-btn");
  const latInput = document.getElementById("lat-input");
  const lonInput = document.getElementById("lon-input");

  if (!form || !btn || !latInput || !lonInput) return;

  form.addEventListener("submit", (e) => {
    // если координаты уже есть – просто отправляем
    if (latInput.value && lonInput.value) {
      return;
    }

    e.preventDefault();

    if (!navigator.geolocation) {
      alert("Браузер не поддерживает геолокацию. Включите её вручную.");
      return;
    }

    btn.disabled = true;
    btn.textContent = "Получение геолокации...";

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        latInput.value = pos.coords.latitude.toString();
        lonInput.value = pos.coords.longitude.toString();
        form.submit();
      },
      (err) => {
        console.error(err);
        alert("Не удалось получить геолокацию. Разрешите доступ и попробуйте ещё раз.");
        btn.disabled = false;
        btn.textContent = "Отметиться";
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  });
});
