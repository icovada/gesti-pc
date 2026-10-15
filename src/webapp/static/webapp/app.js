// Pulsanti che aprono una finestra di conferma (<dialog>).
document.addEventListener("click", (event) => {
  const trigger = event.target.closest("[data-open-dialog]");
  if (!trigger) return;
  const dialog = document.getElementById(trigger.dataset.openDialog);
  if (dialog) dialog.showModal();
});

// Integrazione con Telegram Mini App: tema, pulsante "indietro", espansione.
(function () {
  const tg = window.Telegram && window.Telegram.WebApp;
  // Lo script di Telegram è caricato anche nel browser: initData è vuoto fuori da Telegram.
  const inTelegram = !!(tg && tg.initData);
  window.GestiPC = { tg: tg, inTelegram: inTelegram };
  if (!inTelegram) return;

  const root = document.documentElement;
  root.classList.add("tg");
  const applyTheme = () => root.setAttribute("data-theme", tg.colorScheme === "dark" ? "dark" : "light");
  applyTheme();
  tg.onEvent("themeChanged", () => {
    applyTheme();
    document.dispatchEvent(new CustomEvent("gestipc:themechange"));
  });

  tg.ready();
  tg.expand();

  if (document.body.dataset.back) {
    tg.BackButton.show();
    tg.BackButton.onClick(() => { window.location.href = document.body.dataset.back; });
  } else {
    tg.BackButton.hide();
  }
})();
