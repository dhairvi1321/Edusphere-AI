/* ===== 1. MOBILE NAV ===== */
const hamburger = document.querySelector('.hamburger');
const navLinks = document.querySelector('.nav-links');

if (hamburger && navLinks) {
    hamburger.addEventListener('click', () => {
        navLinks.classList.toggle('active');
        hamburger.setAttribute('aria-expanded', navLinks.classList.contains('active'));
    });
}

document.querySelectorAll('.nav-links a').forEach(link => {
    link.addEventListener('click', () => navLinks.classList.remove('active'));
});

/* ===== 2. SMOOTH SCROLL ===== */
document.querySelectorAll('a[href^="#"]').forEach(link => {
    link.addEventListener('click', function (e) {
        const id = this.getAttribute('href');
        if (!id || id === '#') return;
        const target = document.querySelector(id);
        if (target) {
            e.preventDefault();
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    });
});

/* ===== 3. NAVBAR SCROLL ===== */
const navbar = document.querySelector('.navbar');
window.addEventListener('scroll', () => {
    if (!navbar) return;
    navbar.classList.toggle('scrolled', window.scrollY > 20);
});

/* ===== 4. PARTICLE CANVAS ===== */
const canvas = document.getElementById('hero-canvas');
if (canvas) {
    const ctx = canvas.getContext('2d');
    let particles = [];
    let W, H;

    function resize() {
        W = canvas.width = canvas.offsetWidth;
        H = canvas.height = canvas.offsetHeight;
    }

    resize();
    window.addEventListener('resize', resize);

    const COLORS = ['#6366f1', '#a78bfa', '#22d3ee', '#818cf8'];

    class Particle {
        constructor() { this.reset(); }
        reset() {
            this.x = Math.random() * W;
            this.y = Math.random() * H;
            this.r = Math.random() * 1.8 + 0.4;
            this.vx = (Math.random() - 0.5) * 0.4;
            this.vy = (Math.random() - 0.5) * 0.4;
            this.alpha = Math.random() * 0.5 + 0.1;
            this.color = COLORS[Math.floor(Math.random() * COLORS.length)];
        }
        update() {
            this.x += this.vx;
            this.y += this.vy;
            if (this.x < 0 || this.x > W || this.y < 0 || this.y > H) this.reset();
        }
        draw() {
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.r, 0, Math.PI * 2);
            ctx.fillStyle = this.color;
            ctx.globalAlpha = this.alpha;
            ctx.fill();
        }
    }

    for (let i = 0; i < 90; i++) particles.push(new Particle());

    function drawLines() {
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < 110) {
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.strokeStyle = '#6366f1';
                    ctx.globalAlpha = (1 - dist / 110) * 0.12;
                    ctx.lineWidth = 0.6;
                    ctx.stroke();
                }
            }
        }
    }

    function animate() {
        ctx.clearRect(0, 0, W, H);
        particles.forEach(p => { p.update(); p.draw(); });
        drawLines();
        ctx.globalAlpha = 1;
        requestAnimationFrame(animate);
    }

    animate();
}

/* ===== 5. SCROLL REVEAL ===== */
const revealEls = document.querySelectorAll(
    '.feature-card, .step-card, .problem-card, .benefits-list li, .trust-item, .ai-session'
);

const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry, i) => {
        if (entry.isIntersecting) {
            setTimeout(() => entry.target.classList.add('visible'), i * 60);
            observer.unobserve(entry.target);
        }
    });
}, { threshold: 0.1 });

revealEls.forEach(el => {
    el.classList.add('reveal');
    observer.observe(el);
});

/* ===== 6. TYPING EFFECT ON HERO ===== */
const heroHeading = document.querySelector('.hero h1');
if (heroHeading) {
    const gradSpan = heroHeading.querySelector('.gradient-text');
    if (gradSpan) {
        const words = ['Smarter with AI.', 'Organized.', 'Powered Up.'];
        let wi = 0, ci = 0, deleting = false;

        function type() {
            const word = words[wi];
            if (!deleting) {
                gradSpan.textContent = word.slice(0, ++ci);
                if (ci === word.length) {
                    deleting = true;
                    setTimeout(type, 2000);
                    return;
                }
            } else {
                gradSpan.textContent = word.slice(0, --ci);
                if (ci === 0) {
                    deleting = false;
                    wi = (wi + 1) % words.length;
                }
            }
            setTimeout(type, deleting ? 55 : 90);
        }

        setTimeout(type, 1200);
    }
}

/* ===== 7. PROGRESS BAR ANIMATION ===== */
const progressBar = document.querySelector('.progress-bar');
if (progressBar) {
    const io = new IntersectionObserver(([entry]) => {
        if (entry.isIntersecting) {
            progressBar.style.width = progressBar.style.width || '68%';
            io.disconnect();
        }
    });
    io.observe(progressBar);
}

/* ===== 8. CURRENT YEAR ===== */
const yearEl = document.querySelector('#current-year');
if (yearEl) yearEl.textContent = new Date().getFullYear();

console.log('EduSphere AI loaded.');
