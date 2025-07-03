// Near-Live Dashboard Auto-Refresh Script
// Add this to your dashboard.html template

function initNearLiveUpdates() {
    let refreshInterval = 45000; // 45 seconds
    let isUpdating = false;
    
    function updateDashboardData() {
        if (isUpdating) {
            console.log('Update already in progress, skipping...');
            return;
        }
        
        isUpdating = true;
        console.log('🔄 Fetching near-live market data...');
        
        fetch('/api/live-data')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('📊 Received fresh data:', data);
                
                // Update VIX chart
                if (data.vix && data.vix.length > 0) {
                    updateChart('vix', data.vix);
                    updatePriceDisplay('vix', data.vix[data.vix.length - 1]);
                }
                
                // Update DXY chart
                if (data.dxy && data.dxy.length > 0) {
                    updateChart('dxy', data.dxy);
                    updatePriceDisplay('dxy', data.dxy[data.dxy.length - 1]);
                }
                
                // Update EUR/USD chart
                if (data.eurusd && data.eurusd.length > 0) {
                    updateChart('eurusd', data.eurusd);
                    updatePriceDisplay('eurusd', data.eurusd[data.eurusd.length - 1]);
                }
                
                // Update timestamp
                const timestamp = new Date(data.timestamp).toLocaleTimeString();
                document.getElementById('lastUpdate').textContent = timestamp;
                
                console.log('✅ Dashboard updated successfully');
                
            })
            .catch(error => {
                console.error('❌ Error updating dashboard:', error);
                // Show error indicator
                document.getElementById('lastUpdate').textContent = 'Update failed - ' + new Date().toLocaleTimeString();
            })
            .finally(() => {
                isUpdating = false;
            });
    }
    
    function updateChart(symbol, data) {
        // This function should update your specific chart library
        // Adapt this to your chart implementation (Chart.js, Plotly, etc.)
        console.log(`Updating ${symbol} chart with ${data.length} points`);
        
        // Example for Chart.js:
        // if (window.charts && window.charts[symbol]) {
        //     const chart = window.charts[symbol];
        //     chart.data.labels = data.map(d => new Date(d.Datetime).toLocaleTimeString());
        //     chart.data.datasets[0].data = data.map(d => d.Close);
        //     chart.update('active');
        // }
    }
    
    function updatePriceDisplay(symbol, latestData) {
        // Update current price display
        const priceElement = document.getElementById(`${symbol}Price`);
        const changeElement = document.getElementById(`${symbol}Change`);
        
        if (priceElement && latestData) {
            priceElement.textContent = latestData.Close.toFixed(symbol === 'eurusd' ? 5 : 2);
            
            // Calculate change percentage if possible
            if (changeElement && latestData.Open) {
                const change = ((latestData.Close - latestData.Open) / latestData.Open * 100);
                changeElement.textContent = `${change >= 0 ? '+' : ''}${change.toFixed(2)}%`;
                changeElement.className = `price-change ${change >= 0 ? 'price-up' : 'price-down'}`;
            }
        }
    }
    
    // Start auto-refresh
    console.log(`🚀 Starting near-live updates every ${refreshInterval/1000} seconds`);
    
    // Initial update
    updateDashboardData();
    
    // Set up periodic updates
    setInterval(updateDashboardData, refreshInterval);
    
    // Update timestamp display every 5 seconds
    setInterval(() => {
        if (!isUpdating) {
            const lastUpdateElement = document.getElementById('lastUpdate');
            if (lastUpdateElement && !lastUpdateElement.textContent.includes('failed')) {
                lastUpdateElement.textContent = new Date().toLocaleTimeString();
            }
        }
    }, 5000);
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initNearLiveUpdates);
