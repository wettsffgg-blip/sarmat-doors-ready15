// SARMAT DOORS — PDF delivery hardening patch
// Append this block at the very end of index(7).html (after existing scripts).
(function () {
  async function readPdfResponse(response) {
    const type = (response.headers.get('content-type') || '').toLowerCase();
    const bytes = new Uint8Array(await response.arrayBuffer());
    const magic = new TextDecoder().decode(bytes.slice(0, 5));
    if (!response.ok) {
      let msg = `HTTP ${response.status}`;
      if (type.includes('text/html')) msg += ' — Render вернул HTML вместо API-ответа';
      throw new Error(msg);
    }
    if (magic !== '%PDF-') {
      if (type.includes('text/html')) {
        throw new Error('Render вернул HTML вместо PDF. Проверьте, что новый server.py задеплоен.');
      }
      throw new Error('Сервер вернул не PDF.');
    }
    return new Blob([bytes], { type: 'application/pdf' });
  }

  window.downloadPdf = async function () {
    try {
      if (!order.length) {
        const x = getCurrent();
        if (!x) return;
        order = [x];
        save();
        renderOrder();
      } else if (!ensureCurrent()) return;

      const cu = customer();
      if (!cu) return;

      const r = await fetch('/api/final-pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-cache' },
        cache: 'no-store',
        body: JSON.stringify({ order, orderId, customer: cu })
      });

      const blob = await readPdfResponse(r);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${orderId}_SARMAT_DOORS.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1500);
      toast('✅ Утверждённое КП скачано');
    } catch (e) {
      toast('❌ ' + e.message);
    }
  };

  // Keep the existing Telegram workflow, but never blindly parse an HTML
  // Render error page as JSON.
  window.sendOrder = async function () {
    if (!order.length) {
      const x = getCurrent();
      if (!x) return;
      order = [x];
      save();
      renderOrder();
    } else if (!ensureCurrent()) return;

    const cu = customer();
    if (!cu) return;

    const btn = document.getElementById('send');
    if (btn) {
      btn.disabled = true;
      btn.textContent = 'Отправляем…';
    }

    try {
      const r = await fetch('/api/order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-cache' },
        cache: 'no-store',
        body: JSON.stringify({ order, orderId, customer: cu })
      });

      const type = (r.headers.get('content-type') || '').toLowerCase();
      const text = await r.text();

      let data = null;
      if (type.includes('application/json')) {
        try { data = JSON.parse(text); } catch (_) {}
      }

      if (!r.ok) {
        throw new Error(data && data.error ? data.error : `Ошибка сервера HTTP ${r.status}`);
      }

      if (!data || !data.ok) {
        if (type.includes('text/html')) {
          throw new Error('Render вернул HTML вместо ответа API. Заявка могла уйти в Telegram, но серверный ответ нужно проверить.');
        }
        throw new Error((data && data.error) || 'Ошибка отправки');
      }

      const totalQty = order.reduce((s, x) => s + Number(x.qty || 0), 0);
      const target = document.getElementById('pdfContent');
      if (target) {
        target.innerHTML =
          '<div class="success-box"><h2>✅ Заявка отправлена</h2>' +
          '<p><b>Номер заявки:</b> ' + orderId + '</p>' +
          '<p>Заказ на ' + totalQty + ' дверей передан в рабочий Telegram-чат SARMAT DOORS B2B.</p>' +
          '<p>PDF коммерческого предложения сформирован по утверждённому шаблону.</p>' +
          '<p><button class="btn btn-primary" type="button" onclick="downloadPdf()">📄 Скачать PDF</button></p></div>';
      }
      const modal = document.getElementById('modal');
      if (modal) modal.classList.add('show');
      toast('✅ Заявка отправлена в Telegram');
    } catch (e) {
      toast('❌ ' + e.message);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = 'Сформировать заказ';
      }
    }
  };
})();
