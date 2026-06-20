import { Canvas } from "@react-three/fiber";
import { Grid, OrbitControls } from "@react-three/drei";

/**
 * Minimal grey 3D world placeholder.
 *
 * This is the foundation-level scene: a flat grey ground with a reference grid
 * and orbit controls. Group-scoped map state and generated objects are added in
 * later roadmap sections.
 */
export function WorldMap() {
  return (
    <div className="relative h-full w-full">
      <Canvas
        camera={{ position: [6, 6, 6], fov: 50 }}
        dpr={[1, 2]}
        style={{ width: "100%", height: "100%" }}
      >
        <color attach="background" args={["#1a1a1a"]} />
        <ambientLight intensity={0.6} />
        <directionalLight position={[5, 10, 5]} intensity={1.2} />

        <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
          <planeGeometry args={[50, 50]} />
          <meshStandardMaterial color="#3a3a3a" />
        </mesh>

        <Grid
          args={[50, 50]}
          cellColor="#4a4a4a"
          sectionColor="#5a5a5a"
          infiniteGrid
          fadeDistance={40}
        />

        <OrbitControls enableDamping makeDefault />
      </Canvas>

      {/* Title overlay. pointer-events-none lets mouse drags fall through to
          OrbitControls so the scene stays interactive. */}
      <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
        <h1 className="text-center text-5xl font-bold tracking-tight text-white drop-shadow-lg sm:text-6xl">
          Generate Your World
        </h1>
      </div>
    </div>
  );
}
