// static/js/student.js

// === Переключение языка (RU / KZ) ===
function setLang(code) {
  // Ставим cookie lang на 1 год
  var maxAge = 60 * 60 * 24 * 365;
  document.cookie =
    "lang=" + encodeURIComponent(code) +
    ";path=/;max-age=" + maxAge.toString();

  // Перезагружаем текущую страницу (тот же URL, без прыжков)
  window.location.reload();
}


// === Геолокация для отметки посещаемости (страница студента) ===
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("mark-form");
  const btn = document.getElementById("mark-btn");
  const latInput = document.getElementById("lat-input");
  const lonInput = document.getElementById("lon-input");

  // Если на странице нет формы отметки – просто ничего не делаем
  if (!form || !btn || !latInput || !lonInput) {
    return;
  }

  form.addEventListener("submit", (e) => {
    // Если координаты уже есть, просто отправляем форму
    if (latInput.value && lonInput.value) {
      return;
    }

    e.preventDefault();

    if (!navigator.geolocation) {
      alert("Браузер не поддерживает геолокацию. Включите её вручную.");
      return;
    }

    const originalText = btn.textContent;
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
        btn.textContent = originalText;
      },
      {
        enableHighAccuracy: true,
        timeout: 10000
      }
    );
  });
});
