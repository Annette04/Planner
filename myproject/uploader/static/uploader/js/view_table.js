function showMaterials(orderNumber) {
    fetch(`/materials/${orderNumber}/`)
        .then(response => response.json())
        .then(data => {
            document.getElementById('modalOrderNumber').textContent = data.order_number;
            document.getElementById('modalCount').innerHTML = `Найдено материалов: <b>${data.count}</b>`;

            let html = '<table style="width:100%"><thead><tr>';
            data.columns.forEach(col => {
                html += `<th>${col}</th>`;
            });
            html += '</tr></thead><tbody>';

            data.materials.forEach(row => {
                html += '<tr>';
                data.columns.forEach(col => {
                    html += `<td>${row[col] || '—'}</td>`;
                });
                html += '</tr>';
            });
            html += '</tbody></table>';

            document.getElementById('modalTableContainer').innerHTML = html;
            document.getElementById('materialsModal').style.display = 'block';
        })
        .catch(err => alert('Ошибка при загрузке материалов'));
}

function closeModal() {
    document.getElementById('materialsModal').style.display = 'none';
}

window.onclick = function(event) {
    const modal = document.getElementById('materialsModal');
    if (event.target === modal) {
        closeModal();
    }
}