# Cube
3D Cube Grid Generation and Management System - 3D立方体网格生成与管理系统
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>9x9x9 空间网格与节点 3D 可视化</title>
    <style>
        body { margin: 0; background-color: #111; color: #fff; font-family: sans-serif; }
        #info {
            position: absolute;
            top: 10px;
            left: 10px;
            background: rgba(0, 0, 0, 0.7);
            padding: 10px;
            border-radius: 5px;
            pointer-events: none;
        }
        canvas { display: block; }
    </style>
</head>
<body>
    <div id="info">
        <h3>9x9x9 空间网格系统</h3>
        <p>提示：使用鼠标左键旋转，右键平移，滚轮缩放。</p>
    </div>

    <!-- 引入 Three.js -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script>
        // 1. 初始化场景、相机和渲染器
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        document.body.appendChild(renderer.domElement);

        // 2. 添加灯光
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        scene.add(ambientLight);
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(10, 20, 15);
        scene.add(directionalLight);

        // 3. 创建 9x9x9 空间网格与立方体节点
        const group = new THREE.Group();
        
        // 为了防止 729 个实心方块导致浏览器卡顿，这里采用线框立方体或节点群展示
        const gridSize = 9;
        const spacing = 1.2; // 间距
        const offset = (gridSize * spacing) / 2;

        const boxGeo = new THREE.BoxGeometry(0.8, 0.8, 0.8);
        const wireMat = new THREE.MeshBasicMaterial({ color: 0x00ffcc, wireframe: true });

        for (let x = 0; x < gridSize; x++) {
            for (let y = 0; y < gridSize; y++) {
                for (let z = 0; z < gridSize; z++) {
                    const cube = new THREE.Mesh(boxGeo, wireMat);
                    // 计算每个立方体的中心坐标，使其在空间中居中
                    cube.position.set(
                        x * spacing - offset,
                        y * spacing - offset,
                        z * spacing - offset
                    );
                    group.add(cube);
                }
            }
        }
        scene.add(group);

        // 4. 设置相机位置
        camera.position.set(20, 20, 20);
        camera.lookAt(0, 0, 0);

        // 5. 简单的鼠标交互旋转控制
        let isDragging = false;
        let previousMousePosition = { x: 0, y: 0 };

        document.addEventListener('mousedown', (e) => {
            isDragging = true;
            previousMousePosition = { x: e.clientX, y: e.clientY };
        });

        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            const deltaX = e.clientX - previousMousePosition.x;
            const deltaY = e.clientY - previousMousePosition.y;

            group.rotation.y += deltaX * 0.005;
            group.rotation.x += deltaY * 0.005;

            previousMousePosition = { x: e.clientX, y: e.clientY };
        });

        document.addEventListener('mouseup', () => { isDragging = false; });

        // 6. 动画渲染循环
        function animate() {
            requestAnimationFrame(animate);
            // 可选：让网格微微自转
            // group.rotation.y += 0.001;
            renderer.render(scene, camera);
        }
        animate();

        // 7. 自适应窗口大小
        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });
    </script>
</body>
</html>
