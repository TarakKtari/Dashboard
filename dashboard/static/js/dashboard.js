// Example: Fetch fixing data from backend and populate cards
// You can replace URLs with your actual API endpoints

document.addEventListener('DOMContentLoaded', function() {
    fetch('/admin/api/last-fixing')
        .then(res => res.json())
        .then(data => {
            document.getElementById('last-fixing').innerHTML = `
                <div>EUR: <b>${data.EUR}</b></div>
                <div>USD: <b>${data.USD}</b></div>
            `;
        });
    fetch('/admin/api/live-fixing')
        .then(res => res.json())
        .then(data => {
            document.getElementById('live-fixing').innerHTML = `
                <div>EUR: <b>${data.EUR}</b></div>
                <div>USD: <b>${data.USD}</b></div>
            `;
        });
    fetch('/admin/api/adjusted-rate')
        .then(res => res.json())
        .then(data => {
            document.getElementById('adjusted-rate').innerHTML = `
                <div>EUR: <b>${data.EUR}</b></div>
                <div>USD: <b>${data.USD}</b></div>
            `;
        });
});
