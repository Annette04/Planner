function showMaterials(orderNumber) {
    fetch(`/materials/${encodeURIComponent(orderNumber)}/`)
        .then(response => {
            if (!response.ok) throw new Error('Ошибка сети');
            return response.json();
        })
        .then(data => {
            document.getElementById('modalOrderNumber').textContent = data.order_number;
            document.getElementById('modalCount').innerHTML = `Найдено позиций: <b>${data.count}</b>`;

            let html = `
                <table style="width:100%">
                    <thead>
                        <tr>
                            <th>Материал</th>
                            <th>Краткий текст материала</th>
                            <th>ПланКоличество</th>
                            <th>Доступно на складе</th>
                        </tr>
                    </thead>
                    <tbody>`;

            if (data.count === 0) {
                html += `<tr><td colspan="5" style="text-align:center; padding:30px;">Материалы не найдены</td></tr>`;
            } else {
                data.materials.forEach(row => {
                    const isEnough = row['Недостаток'] === 0;
                    const rowClass = isEnough ? 'status-green' : 'status-red';

                    html += `<tr class="${rowClass}">`;
                    html += `<td>${row['Материал'] || '—'}</td>`;
                    html += `<td>${row['Краткий текст материала'] || '—'}</td>`;
                    html += `<td>${row['ПланКоличество'] || '—'}</td>`;
                    html += `<td>${row['Доступно на складе'] || '—'}</td>`;
                    html += `</tr>`;
                });
            }
            html += `</tbody></table>`;

            document.getElementById('modalTableContainer').innerHTML = html;
            document.getElementById('materialsModal').style.display = 'block';
        })
        .catch(err => {
            console.error(err);
            alert('Не удалось загрузить материалы');
        });
}

function closeModal() {
    document.getElementById('materialsModal').style.display = 'none';
}

window.onclick = function(event) {
    const modal = document.getElementById('materialsModal');
    if (event.target === modal) closeModal();
}