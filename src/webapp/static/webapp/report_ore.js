// Grafici del report ore (Chart.js). I dati arrivano dal template via json_script.
(function () {
  const data = JSON.parse(document.getElementById("chart-data").textContent);
  const nf = new Intl.NumberFormat("it-IT", { maximumFractionDigits: 1 });
  const fmtOre = (v) => nf.format(v) + " h";
  const charts = [];

  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  function baseOptions(t) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false }, // legenda HTML sopra il grafico
        tooltip: {
          backgroundColor: t.surface,
          titleColor: t.text,
          bodyColor: t.text2,
          borderColor: t.border,
          borderWidth: 1,
          padding: 10,
          boxPadding: 4,
          usePointStyle: true,
        },
      },
    };
  }

  function axis(t, extra) {
    return Object.assign(
      {
        grid: { color: t.grid, drawTicks: false },
        border: { display: false },
        ticks: { color: t.text3, padding: 6, font: { size: 12 } },
      },
      extra
    );
  }

  function render() {
    charts.splice(0).forEach((c) => c.destroy());
    const t = {
      surface: css("--surface"), text: css("--text"), text2: css("--text-2"),
      text3: css("--text-3"), grid: css("--grid"), border: css("--border"),
      series: [css("--series-1"), css("--series-2"), css("--series-3")],
    };

    // Ore per mese, impilate per categoria.
    const mesiEl = document.getElementById("chart-mesi");
    if (mesiEl) {
      const opts = baseOptions(t);
      opts.plugins.tooltip.callbacks = {
        label: (ctx) => ` ${ctx.dataset.label}: ${fmtOre(ctx.parsed.y)}`,
        footer: (items) => "Totale: " + fmtOre(items.reduce((s, i) => s + i.parsed.y, 0)),
      };
      opts.plugins.tooltip.footerColor = t.text;
      opts.scales = {
        x: axis(t, { stacked: true, grid: { display: false }, ticks: { color: t.text3, padding: 6, maxRotation: 0, autoSkip: true, autoSkipPadding: 8 } }),
        y: axis(t, { stacked: true, beginAtZero: true, ticks: { color: t.text3, padding: 6, callback: (v) => nf.format(v) + " h" } }),
      };
      charts.push(new Chart(mesiEl, {
        type: "bar",
        data: {
          labels: data.mesi.map((m) => m.label),
          datasets: data.categorie.map((c, i) => ({
            label: c.label,
            data: data.mesi.map((m) => Math.round(m[c.key] * 100) / 100),
            backgroundColor: t.series[i],
            borderColor: t.surface,
            borderWidth: { top: 2 },
            borderSkipped: "bottom",
            borderRadius: 0,
            maxBarThickness: 40,
          })),
        },
        options: opts,
      }));
    }

    // Ore per volontario (barre orizzontali, ordinate).
    const volEl = document.getElementById("chart-volontari");
    if (volEl && data.volontari.length) {
      volEl.parentElement.style.height = Math.max(160, data.volontari.length * 30 + 40) + "px";
      const opts = baseOptions(t);
      opts.indexAxis = "y";
      opts.interaction = { mode: "nearest", axis: "y", intersect: false };
      opts.plugins.tooltip.callbacks = { label: (ctx) => " " + fmtOre(ctx.parsed.x) };
      opts.scales = {
        x: axis(t, { beginAtZero: true, position: "top", ticks: { color: t.text3, callback: (v) => nf.format(v) + " h" } }),
        y: axis(t, { grid: { display: false }, ticks: { color: t.text2, font: { size: 13 } } }),
      };
      charts.push(new Chart(volEl, {
        type: "bar",
        data: {
          labels: data.volontari.map((v) => v.nome),
          datasets: [{
            label: "Ore",
            data: data.volontari.map((v) => v.ore),
            backgroundColor: t.series[0],
            borderRadius: 4,
            borderSkipped: "start",
            barThickness: 16,
          }],
        },
        options: opts,
      }));
    }
  }

  render();
  document.addEventListener("gestipc:themechange", render);
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);
})();
