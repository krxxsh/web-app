// AI Sched - Client Side Logic
console.log("AI Sched Engine Initialized");

// Global utility for premium interactions
document.addEventListener('mousemove', (e) => {
    const glow = document.querySelector('.cursor-glow');
    if (glow) {
        glow.style.left = e.pageX + 'px';
        glow.style.top = e.pageY + 'px';
    }
});
