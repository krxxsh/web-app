/**
 * AI Sched: Hero 3D Scene
 * High-performance abstract 3D geometry using Vanilla Three.js
 */

const initHero3D = () => {
    const container = document.getElementById('hero-canvas-container');
    if (!container) return;

    // SCENE SETUP
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });

    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // GEOMETRY: Abstract Particles / Grid
    const geometry = new THREE.SphereGeometry(1.5, 32, 32);
    const material = new THREE.MeshPhongMaterial({
        color: 0x1d76f2,
        wireframe: true,
        transparent: true,
        opacity: 0.3
    });
    const sphere = new THREE.Mesh(geometry, material);
    scene.add(sphere);

    // Dynamic Nodes (Floating Particles)
    const particlesCount = 500;
    const particlesGeometry = new THREE.BufferGeometry();
    const posArray = new Float32Array(particlesCount * 3);

    for (let i = 0; i < particlesCount * 3; i++) {
        posArray[i] = (Math.random() - 0.5) * 8;
    }

    particlesGeometry.setAttribute('position', new THREE.BufferAttribute(posArray, 3));
    const particlesMaterial = new THREE.PointsMaterial({
        size: 0.005,
        color: 0xffffff,
        transparent: true,
        opacity: 0.8
    });
    const particlesMesh = new THREE.Points(particlesGeometry, particlesMaterial);
    scene.add(particlesMesh);

    // LIGHTING
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
    scene.add(ambientLight);

    const pointLight = new THREE.PointLight(0x1d76f2, 2);
    pointLight.position.set(2, 3, 4);
    scene.add(pointLight);

    camera.position.z = 3;

    // ANIMATION & INTERACTION
    let mouseX = 0;
    let mouseY = 0;

    document.addEventListener('mousemove', (e) => {
        mouseX = (e.clientX / window.innerWidth) - 0.5;
        mouseY = (e.clientY / window.innerHeight) - 0.5;
    });

    const clock = new THREE.Clock();

    const animate = () => {
        const elapsedTime = clock.getElapsedTime();

        // Rotate Sphere
        sphere.rotation.y = elapsedTime * 0.1;
        sphere.rotation.x = elapsedTime * 0.05;

        // Mouse Parallax
        sphere.position.x = mouseX * 0.5;
        sphere.position.y = -mouseY * 0.5;

        particlesMesh.rotation.y = -elapsedTime * 0.02;

        renderer.render(scene, camera);
        window.requestAnimationFrame(animate);
    };

    // HANDLE RESIZE
    window.addEventListener('resize', () => {
        camera.aspect = container.clientWidth / container.clientHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(container.clientWidth, container.clientHeight);
    });

    animate();
};

document.addEventListener('DOMContentLoaded', initHero3D);
