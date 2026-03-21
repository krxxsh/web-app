/**
 * AI Sched: Elite 3D Tilt Utility (Vanilla JS)
 * Version: 1.0
 * Purpose: Provides a high-performance 3D tilt effect for card-like elements.
 */

document.addEventListener('DOMContentLoaded', () => {
    const tiltElements = document.querySelectorAll('.card, .glass-card, .glass-panel');

    const handleTilt = (e, el) => {
        const rect = el.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        const centerX = rect.width / 2;
        const centerY = rect.height / 2;

        // Calculate rotation degrees (max 10deg)
        const rotateY = ((x - centerX) / centerX) * 10;
        const rotateX = ((centerY - y) / centerY) * 10;

        el.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale3d(1.02, 1.02, 1.02)`;
        
        // Add dynamic shadow depth
        const shadowX = (x - centerX) / 10;
        const shadowY = (y - centerY) / 10;
        el.style.boxShadow = `${-shadowX}px ${-shadowY}px 40px rgba(0,0,0,0.5), var(--neon-glow)`;
    };

    const resetTilt = (el) => {
        el.style.transform = `perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)`;
        el.style.boxShadow = 'var(--glass-shadow)';
    };

    tiltElements.forEach(el => {
        // Ensure initial 3D state
        el.style.transition = 'transform 0.15s ease-out, box-shadow 0.15s ease-out';
        el.style.transformStyle = 'preserve-3d';

        el.addEventListener('mousemove', (e) => handleTilt(e, el));
        el.addEventListener('mouseleave', () => resetTilt(el));
        
        // Mobile support: slight tilt on touch
        el.addEventListener('touchstart', (e) => {
            const touch = e.touches[0];
            handleTilt(touch, el);
        }, { passive: true });
        el.addEventListener('touchend', () => resetTilt(el));
    });

    // Elite 3D Parallax Logic
    window.addEventListener('scroll', () => {
        const scrolled = window.pageYOffset;
        document.querySelectorAll('[data-parallax-depth]').forEach(el => {
            const depth = el.getAttribute('data-parallax-depth') || 0;
            const yPos = -(scrolled * depth / 100);
            el.style.transform = `perspective(1000px) translateY(${yPos}px) translateZ(${depth}px)`;
        });
    });
});
